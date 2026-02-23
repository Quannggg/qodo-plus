import pytest
from fastapi.testclient import TestClient
from app import app
from datetime import date
from unittest.mock import patch

client = TestClient(app)


def test_root():
    """
    Test the root endpoint by sending a GET request to "/" and checking the response status code and JSON body.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the FastAPI application!"}


def test_square():
    """
    Test the square endpoint with various integer inputs.
    """
    # Test positive number
    response = client.get("/square/5")
    assert response.status_code == 200
    assert response.json() == {"result": 25}
    
    # Test negative number
    response = client.get("/square/-3")
    assert response.status_code == 200
    assert response.json() == {"result": 9}
    
    # Test zero
    response = client.get("/square/0")
    assert response.status_code == 200
    assert response.json() == {"result": 0}


def test_is_palindrome():
    """
    Test the is_palindrome endpoint with various string inputs.
    """
    # Test with palindrome
    response = client.get("/is-palindrome/racecar")
    assert response.status_code == 200
    assert response.json() == {"is_palindrome": True}
    
    # Test with non-palindrome
    response = client.get("/is-palindrome/hello")
    assert response.status_code == 200
    assert response.json() == {"is_palindrome": False}
    
    # Test with empty string (empty string is a palindrome)
    # The endpoint expects a path parameter, so we need to provide an empty string as the parameter
    response = client.get("/is-palindrome/%20")  # URL-encoded space to represent empty string
    assert response.status_code == 200
    assert response.json() == {"is_palindrome": True}
    
    # Test with single character
    response = client.get("/is-palindrome/a")
    assert response.status_code == 200
    assert response.json() == {"is_palindrome": True}
    
    # Test with case-sensitive palindrome
    response = client.get("/is-palindrome/Racecar")
    assert response.status_code == 200
    assert response.json() == {"is_palindrome": False}


def test_sqrt_endpoint():
    """
    Test the sqrt endpoint with various inputs including valid and invalid cases.
    """
    # Test with positive number
    response = client.get("/sqrt/16")
    assert response.status_code == 200
    assert response.json() == {"result": 4.0}
    
    # Test with zero
    response = client.get("/sqrt/0")
    assert response.status_code == 200
    assert response.json() == {"result": 0.0}
    
    # Test with negative number (should raise HTTPException)
    response = client.get("/sqrt/-4")
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot take square root of a negative number"}
    
    # Test with decimal number
    response = client.get("/sqrt/2.25")
    assert response.status_code == 200
    assert response.json() == {"result": 1.5}


def test_divide_by_zero():
    """
    Test the divide endpoint with zero denominator to ensure proper error handling.
    """
    response = client.get("/divide/10/0")
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}
    
    response = client.get("/divide/0/0")
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


def test_divide_valid():
    """
    Test the divide endpoint with valid integer inputs.
    """
    response = client.get("/divide/10/2")
    assert response.status_code == 200
    assert response.json() == {"result": 5.0}
    
    response = client.get("/divide/0/5")
    assert response.status_code == 200
    assert response.json() == {"result": 0.0}
    
    response = client.get("/divide/-10/2")
    assert response.status_code == 200
    assert response.json() == {"result": -5.0}


def test_divide():
    """
    Test the divide endpoint with valid division and division by zero error.
    """
    # Test valid division
    response = client.get("/divide/10/2")
    assert response.status_code == 200
    assert response.json() == {"result": 5.0}
    
    # Test division resulting in float
    response = client.get("/divide/5/2")
    assert response.status_code == 200
    assert response.json() == {"result": 2.5}
    
    # Test division by zero raises HTTPException
    response = client.get("/divide/10/0")
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


def test_subtract():
    """
    Test the subtract endpoint with various integer combinations.
    """
    # Test positive numbers
    response = client.get("/subtract/10/4")
    assert response.status_code == 200
    assert response.json() == {"result": 6}
    
    # Test negative result
    response = client.get("/subtract/3/10")
    assert response.status_code == 200
    assert response.json() == {"result": -7}
    
    # Test with negative numbers
    response = client.get("/subtract/-5/-3")
    assert response.status_code == 200
    assert response.json() == {"result": -2}


def test_add():
    """
    Test the add endpoint with various integer combinations.
    """
    # Test positive numbers
    response = client.get("/add/5/3")
    assert response.status_code == 200
    assert response.json() == {"result": 8}
    
    # Test negative numbers
    response = client.get("/add/-5/3")
    assert response.status_code == 200
    assert response.json() == {"result": -2}
    
    # Test zero
    response = client.get("/add/0/0")
    assert response.status_code == 200
    assert response.json() == {"result": 0}


def test_current_date():
    """
    Test the current_date endpoint by sending a GET request to "/current-date"
    and checking the response contains today's date in ISO format.
    """
    response = client.get("/current-date")
    assert response.status_code == 200
    assert response.json() == {"date": date.today().isoformat()}

