import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# The base URL combined from main.py prefix and router prefix
BASE_URL = "/api/v1/products"

def get_unique_order_code():
    """Helper to generate a unique order code for each test run."""
    return f"TEST-{uuid.uuid4().hex[:8].upper()}"

@pytest.fixture
def sample_payload():
    """Fixture to provide a fresh product payload."""
    return {
        "Product_id": "Test Board LPC2148",
        "Order Code": get_unique_order_code(),
        "Category": "Development Board",
        "Brand": "ARM",
        "Price": 15000.0,
        "sections": {
            "Description": "A high-performance testing board.",
            "Features": "- Feature A\n- Feature B"
        }
    }

# ─────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────

def test_create_product(sample_payload):
    """Test adding a new product and verifying the alias mapping."""
    response = client.post(f"{BASE_URL}/", json=sample_payload)
    assert response.status_code == 200
    data = response.json()
    
    # Verify the alias 'Product_id' was correctly mapped to 'name'
    assert data["name"] == sample_payload["Product_id"]
    assert data["order_code"] == sample_payload["Order Code"]
    assert "id" in data

def test_read_all_products(sample_payload):
    """Test fetching the product list."""
    # Ensure at least one product exists
    client.post(f"{BASE_URL}/", json=sample_payload)
    
    response = client.get(f"{BASE_URL}/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1

def test_read_single_product(sample_payload):
    """Test fetching one product by ID."""
    # Create a product to get a valid ID
    create_res = client.post(f"{BASE_URL}/", json=sample_payload)
    prod_id = create_res.json()["id"]

    response = client.get(f"{BASE_URL}/{prod_id}")
    assert response.status_code == 200
    assert response.json()["id"] == prod_id
    assert response.json()["name"] == sample_payload["Product_id"]

def test_update_product(sample_payload):
    """Test editing product details."""
    # Create product
    create_res = client.post(f"{BASE_URL}/", json=sample_payload)
    prod_id = create_res.json()["id"]

    update_payload = {
        "brand": "ARM Enhanced Edition",
        "single_price": 18500.0,
        "sections": {
            "Description": "Updated AI content."
        }
    }
    
    response = client.put(f"{BASE_URL}/{prod_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["brand"] == "ARM Enhanced Edition"
    assert data["single_price"] == 18500.0

def test_delete_product(sample_payload):
    """Test removing a product and ensuring cascade/deletion works."""
    # Create product
    create_res = client.post(f"{BASE_URL}/", json=sample_payload)
    prod_id = create_res.json()["id"]

    # Delete it
    del_res = client.delete(f"{BASE_URL}/{prod_id}")
    assert del_res.status_code == 200
    
    # Verify 404 on subsequent GET
    get_res = client.get(f"{BASE_URL}/{prod_id}")
    assert get_res.status_code == 404

def test_create_duplicate_order_code(sample_payload):
    """Test that duplicate order codes trigger a 400 error."""
    # Create first time
    client.post(f"{BASE_URL}/", json=sample_payload)
    
    # Create second time with exact same Order Code
    response = client.post(f"{BASE_URL}/", json=sample_payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()