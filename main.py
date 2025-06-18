from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, Integer, String, Float
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ECommerceFastAPI",
    description="A secure and scalable e-commerce shopping cart API with JWT authentication, async MySQL queries, and Swagger UI documentation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security settings
SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=0)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# Models
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)
    price = Column(Float)
    stock = Column(Integer)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))

class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    product_id = Column(Integer)
    quantity = Column(Integer)

# Pydantic models
class ProductBase(BaseModel):
    name: str
    price: float
    stock: int

class ProductResponse(ProductBase):
    id: int
    class Config:
        from_attributes = True

class CartItemBase(BaseModel):
    product_id: int
    quantity: int

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    password: str

# Dependencies
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await db.execute(User.__table__.select().where(User.username == username))
    user = user.first()
    if user is None:
        raise credentials_exception
    return user

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error: {exc.status_code} - {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# Authentication
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/token", response_model=Token, summary="User login to obtain JWT token")
@limiter.limit("100/minute")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db), request: Request = None):
    logger.info(f"Login attempt for user: {form_data.username}")
    result = await db.execute(User.__table__.select().where(User.username == form_data.username))
    user = result.first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register", summary="Register a new user")
@limiter.limit("50/minute")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db), request: Request = None):
    logger.info(f"Register attempt for user: {user.username}")
    result = await db.execute(User.__table__.select().where(User.username == user.username))
    if result.first():
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()
    return {"message": "User created successfully"}

# API endpoints
@app.get("/products", response_model=List[ProductResponse], summary="Get all products")
async def get_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(Product.__table__.select())
    return result.scalars().all()

@app.post("/cart", response_model=CartItemBase, summary="Add item to cart")
@limiter.limit("50/minute")
async def add_to_cart(item: CartItemBase, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), request: Request = None):
    logger.info(f"Add to cart attempt for user_id: {user.id}, product_id: {item.product_id}")
    result = await db.execute(Product.__table__.select().where(Product.id == item.product_id))
    product = result.first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.stock < item.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    cart_item = CartItem(user_id=user.id, product_id=item.product_id, quantity=item.quantity)
    db.add(cart_item)
    await db.commit()
    return item

@app.get("/cart", response_model=List[CartItemBase], summary="Get user's cart items")
async def get_cart(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(CartItem.__table__.select().where(CartItem.user_id == user.id))
    return result.scalars().all()

@app.delete("/cart/{item_id}", summary="Remove item from cart")
async def remove_from_cart(item_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logger.info(f"Remove from cart attempt for user_id: {user.id}, item_id: {item_id}")
    result = await db.execute(CartItem.__table__.select().where(CartItem.id == item_id, CartItem.user_id == user.id))
    cart_item = result.first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    await db.execute(CartItem.__table__.delete().where(CartItem.id == item_id))
    await db.commit()
    return {"message": "Item removed from cart"}

@app.patch("/cart/{item_id}", response_model=CartItemBase, summary="Update cart item quantity")
async def update_cart_item(item_id: int, item: CartItemBase, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logger.info(f"Update cart item attempt for user_id: {user.id}, item_id: {item_id}")
    result = await db.execute(CartItem.__table__.select().where(CartItem.id == item_id, CartItem.user_id == user.id))
    cart_item = result.first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    result = await db.execute(Product.__table__.select().where(Product.id == item.product_id))
    product = result.first()
    if not product or product.stock < item.quantity:
        raise HTTPException(status_code=400, detail="Invalid product or insufficient stock")
    await db.execute(CartItem.__table__.update().where(CartItem.id == item_id).values(quantity=item.quantity))
    await db.commit()
    return item

# Initialize database
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup_event():
    await init_db()