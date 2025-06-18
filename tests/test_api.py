import pytest
import httpx
from fastapi.testclient import TestClient
from main import app, get_db, Base, Product, User, CartItem
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# Test database setup
DATABASE_URL = "mysql+asyncmy://user:password@localhost:3306/ecommerce_test"
engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_register_user():
    response = client.post("/register", json={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    assert response.json() == {"message": "User created successfully"}

@pytest.mark.asyncio
async def test_login_success():
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_failure():
    response = client.post("/token", data={"username": "wronguser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_get_products():
    async with TestingSessionLocal() as db:
        product = Product(name="Test Product", price=100.0, stock=50)
        db.add(product)
        await db.commit()
    response = client.get("/products")
    assert response.status_code == 200
    assert len(response.json()) > 0
    assert response.json()[0]["name"] == "Test Product"

@pytest.mark.asyncio
async def test_add_to_cart():
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    token_response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    token = token_response.json()["access_token"]
    
    async with TestingSessionLocal() as db:
        product = Product(name="Test Product", price=100.0, stock=50)
        db.add(product)
        await db.commit()
        await db.refresh(product)
    
    response = client.post(
        "/cart",
        json={"product_id": product.id, "quantity": 2},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["product_id"] == product.id
    assert response.json()["quantity"] == 2

@pytest.mark.asyncio
async def test_add_to_cart_unauthorized():
    response = client.post("/cart", json={"product_id": 1, "quantity": 2})
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

@pytest.mark.asyncio
async def test_remove_from_cart():
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    token_response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    token = token_response.json()["access_token"]
    
    async with TestingSessionLocal() as db:
        product = Product(name="Test Product", price=100.0, stock=50)
        db.add(product)
        await db.commit()
        await db.refresh(product)
        cart_item = CartItem(user_id=1, product_id=product.id, quantity=2)
        db.add(cart_item)
        await db.commit()
        await db.refresh(cart_item)
    
    response = client.delete(f"/cart/{cart_item.id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["message"] == "Item removed from cart"

@pytest.mark.asyncio
async def test_update_cart_item():
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    token_response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    token = token_response.json()["access_token"]
    
    async with TestingSessionLocal() as db:
        product = Product(name="Test Product", price=100.0, stock=50)
        db.add(product)
        await db.commit()
        await db.refresh(product)
        cart_item = CartItem(user_id=1, product_id=product.id, quantity=2)
        db.add(cart_item)
        await db.commit()
        await db.refresh(cart_item)
    
    response = client.patch(
        f"/cart/{cart_item.id}",
        json={"product_id": product.id, "quantity": 3},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 3