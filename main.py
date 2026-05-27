from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.exc import IntegrityError   
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from derms_schemas import UserCreate,UserResponse,TokenResponse,AssetCreate,AssetResponse,AssetStatusUpdate, MetricsResponse
from derms_models import Users, Assets, Base, AssetType, AssetStatus
from derms_db import get_db, engine
from derms_sec import hash_password, verify_password, create_token, ALGORITHM, JWT_SECRET_KEY
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from confluent_kafka import KafkaException, Producer
import os, random, jwt, json, datetime, asyncio

KAFKA_BOOTSTRAP_URL         = os.getenv("KAFKA_BOOTSTRAP_URL", "localhost")
KAFKA_BOOTSTRAP_PORT        = os.getenv("KAFKA_BOOTSTRAP_PORT", "9092")
SIMULATE_ERROR_RATE         = os.getenv("SIMULATE_ERROR_RATE","0")
SIMULATE_SLOW_ENDPOINT_MS   = os.getenv("SIMULATE_SLOW_ENDPOINT_MS", "0")

simulate_error_rate = float(SIMULATE_ERROR_RATE)
simulate_slow_endpoint = int(SIMULATE_SLOW_ENDPOINT_MS)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        sub = jwt.decode(jwt=token, algorithms=[ALGORITHM], key=JWT_SECRET_KEY)
        user = db.query(Users).filter(Users.username == sub["sub"]).first()
    except jwt.ExpiredSignatureError:
       raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Token")
    if user:
        return user
    raise HTTPException(401, detail="User not found")

def delivery_callback(err, msg):
    if err is not None:
        print(f"Broker-side error: {err}")
    else:
        print(
            f"Delivered: "
            f"topic={msg.topic()} "
            f"partition={msg.partition()} "
            f"offset={msg.offset()} "
            f"key={msg.key().decode('utf-8')}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except IntegrityError:
        pass

    app.state.producer = Producer({
        "bootstrap.servers": f"{KAFKA_BOOTSTRAP_URL}:{KAFKA_BOOTSTRAP_PORT}",
        "linger.ms": 5,
        "acks": "all"
    })

    yield

    app.state.producer.flush(10)
    engine.dispose()

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def simulate_conditions(request: Request, call_next):
    if simulate_error_rate and random.random() < simulate_error_rate:
        return JSONResponse(status_code=500, content={"detail": "Simulated error"})
    if simulate_slow_endpoint:
        await asyncio.sleep(simulate_slow_endpoint/1000)
        return await call_next(request)
    return await call_next(request)
    

@app.get('/health')
async def get_health():
    return {
        "Status": "Doing Great, Thanks for checking upon me!!",
        "timestamp": datetime.datetime.now()
    }

@app.post('/register', status_code=status.HTTP_201_CREATED,response_model=UserResponse)
async def create_user(data: UserCreate, db: Session = Depends(get_db)):
    hashed_password = hash_password(data.password)
    user = Users(
        username = data.username,
        hashed_password = hashed_password
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        raise HTTPException(409, detail="Username already exists")
    
@app.post('/login', status_code=status.HTTP_200_OK, response_model=TokenResponse)
def user_login(data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.username==data.username).first()
    if user is None:
        raise HTTPException(404, detail="User not found")
    if verify_password(data.password, user.hashed_password):
        return create_token(data.username)
    else:
        raise HTTPException(401, detail="Invalid Password")
    
@app.post('/assets', status_code=status.HTTP_201_CREATED, response_model=AssetResponse)
def create_asset(data: AssetCreate, db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)):
    asset = Assets(
        name=data.name,
        asset_type=data.asset_type,
        status=data.status,
        owner_id=current_user.id
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

@app.get('/assets', status_code=status.HTTP_200_OK, response_model=list[AssetResponse])
def get_assets(db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)):
    return db.query(Assets).all()

@app.get('/assets/{asset_id}', status_code=status.HTTP_200_OK, response_model=AssetResponse)
def get_asset(asset_id: UUID, db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)):
    asset = db.get(Assets, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset
    
@app.put('/assets/{asset_id}/status', status_code=status.HTTP_200_OK, response_model=AssetResponse)
def update_asset_status(asset_id: UUID, data: AssetStatusUpdate, request: Request ,db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)):
    asset = db.get(Assets, asset_id)
    producer = request.app.state.producer

    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    old_status = asset.status.value
    new_status = data.status.value
    event = {"asset_id": str(asset_id), "old_status": old_status, "new_status": new_status, "timestamp": datetime.datetime.utcnow().isoformat()}

    asset.status = data.status
    db.commit()
    db.refresh(asset)

    try:
        producer.produce(
            topic="asset-status-changes",
            key=str(asset_id).encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
            on_delivery=delivery_callback
        )
        producer.poll(0)
    except KafkaException as e:
        print(f"Failed to queue message for {event['asset_id']}: {e}")

    return asset

@app.get('/metrics', status_code=status.HTTP_200_OK, response_model=MetricsResponse)
def get_metrics(db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)):
    total = db.query(Assets).count()
    active = db.query(Assets).filter(Assets.status == AssetStatus.active).count()
    inactive = db.query(Assets).filter(Assets.status == AssetStatus.inactive).count()
    fault = db.query(Assets).filter(Assets.status == AssetStatus.fault).count()
    maintenance = db.query(Assets).filter(Assets.status == AssetStatus.maintenance).count()
    solar = db.query(Assets).filter(Assets.asset_type == AssetType.solar).count()
    battery = db.query(Assets).filter(Assets.asset_type == AssetType.battery).count()
    ev = db.query(Assets).filter(Assets.asset_type == AssetType.ev).count()
    wind = db.query(Assets).filter(Assets.asset_type == AssetType.wind).count()
    return MetricsResponse(
        total_assets=total,
        active_count=active,
        inactive_count=inactive,
        fault_count=fault,
        maintenance_count=maintenance,
        solar_count=solar,
        battery_count=battery,
        ev_count=ev,
        wind_count=wind
    )
