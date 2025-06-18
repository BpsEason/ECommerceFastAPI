# ECommerceFastAPI

A secure and scalable e-commerce shopping cart API built with FastAPI, MySQL, Bootstrap 5, and Docker. Features JWT authentication, async MySQL queries, pytest tests, and Swagger UI documentation. The frontend, served via Nginx, provides a responsive UI for browsing products and managing the cart.

*GitHub: https://github.com/BpsEason/ECommerceFastAPI*

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy, asyncmy
- **Database**: MySQL
- **Frontend**: Bootstrap 5, Nginx
- **Testing**: pytest, pytest-asyncio, httpx
- **Containerization**: Docker, Docker Compose
- **CI/CD**: GitHub Actions

## Features
- RESTful API for product listing, cart management (add, update, delete)
- JWT-based authentication with bcrypt password hashing
- Asynchronous database queries with connection pooling
- API rate limiting with slowapi
- Logging for request and error tracking
- Responsive frontend with enhanced cart display (product details and totals)
- Automated API tests with pytest
- Interactive API documentation via Swagger UI and ReDoc
- CI/CD pipeline with GitHub Actions

## Prerequisites
- Docker and Docker Compose
- Git
- MySQL client (optional, for manual database setup)

## Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/BpsEason/ECommerceFastAPI.git
   cd ECommerce Collectors
   ```
2. Create a `.env` file with a secure JWT secret:
   ```bash
   echo "JWT_SECRET=$(openssl rand -hex 32)" > .env
   ```
3. Start the application:
   ```bash
   docker-compose up --build
   ```
   - The `init_db` function in `main.py` automatically creates the `products`, `users`, and `cart_items` tables in the `ecommerce` database.
4. (Optional) Initialize test database and sample data for testing:
   - Access the MySQL container:
     ```bash
     docker-compose exec db mysql -uroot -prootpassword
     ```
   - Create the test database and insert sample data:
     ```sql
     CREATE DATABASE ecommerce_test;
     USE ecommerce;
     INSERT INTO products (name, price, stock) VALUES
     ('商品1', 100.0, 50),
     ('商品2', 200.0, 30),
     ('商品3', 150.0, 20);
     ```

## Usage
- **Frontend**: http://localhost:8080
- **API Documentation**: http://localhost:8000/docs (Swagger UI) or http://localhost:8000/redoc (ReDoc)
- **Run Tests**:
   - Ensure the `ecommerce_test` database exists.
   - Execute:
     ```bash
     docker-compose exec api pytest tests/test_api.py -v
     ```
- **Logs**: Check `app.log` for request and error logs.

## API Endpoints
- **POST /token**: Login to obtain JWT token
- **POST /register**: Register a new user
- **GET /products**: List all products
- **POST /cart**: Add item to cart (requires authentication)
- **GET /cart**: View cart items (requires authentication)
- **PATCH /cart/{item_id}**: Update cart item quantity (requires authentication)
- **DELETE /cart/{item_id}**: Remove item from cart (requires authentication)

## Contributing
Contributions are welcome! Please open an issue or submit a pull request on GitHub.

## License
MIT