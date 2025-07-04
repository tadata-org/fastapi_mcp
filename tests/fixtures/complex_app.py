from typing import Optional, List, Dict, Any, Union
from uuid import UUID

from fastapi import FastAPI, Query, Path, Body, Header, Cookie
import pytest

from tests.fixtures.conftest import make_fastapi_app_base

from .types import (
    Product,
    Customer,
    OrderResponse,
    PaginatedResponse,
    ProductCategory,
    OrderRequest,
    ErrorResponse,
)


def make_complex_fastapi_app(
    example_product: Product,
    example_customer: Customer,
    example_order_response: OrderResponse,
    parametrized_config: dict[str, Any] | None = None,
) -> FastAPI:
    app = make_fastapi_app_base(parametrized_config=parametrized_config)

    @app.get(
        "/products",
        response_model=PaginatedResponse,
        tags=["products"],
        operation_id="list_products",
        response_model_exclude_none=True,
    )
    async def list_products(
        category: Optional[ProductCategory] = Query(None, description="Filter by product category"),
        min_price: Optional[float] = Query(None, description="Minimum price filter", gt=0),
        max_price: Optional[float] = Query(None, description="Maximum price filter", gt=0),
        tag: Optional[List[str]] = Query(None, description="Filter by tags"),
        sort_by: str = Query("created_at", description="Field to sort by"),
        sort_direction: str = Query("desc", description="Sort direction (asc or desc)"),
        in_stock_only: bool = Query(False, description="Show only in-stock products"),
        page: int = Query(1, description="Page number", ge=1),
        size: int = Query(20, description="Page size", ge=1, le=100),
        user_agent: Optional[str] = Header(None, description="User agent header"),
    ):
        """
        List products with various filtering, sorting and pagination options.
        Returns a paginated response of products.
        """
        return PaginatedResponse(items=[example_product], total=1, page=page, size=size, pages=1)

    @app.get(
        "/products/{product_id}",
        response_model=Product,
        tags=["products"],
        operation_id="get_product",
        responses={
            404: {"model": ErrorResponse, "description": "Product not found"},
        },
    )
    async def get_product(
        product_id: UUID = Path(..., description="The ID of the product to retrieve"),
        include_unavailable: bool = Query(False, description="Include product even if not available"),
    ):
        """
        Get detailed information about a specific product by its ID.
        Includes all variants, images, and metadata.
        """
        # Just returning the example product with the requested ID
        product_copy = example_product.model_copy()
        product_copy.id = product_id
        return product_copy

    @app.post(
        "/orders",
        response_model=OrderResponse,
        tags=["orders"],
        operation_id="create_order",
        status_code=201,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid order data"},
            404: {"model": ErrorResponse, "description": "Customer or product not found"},
            422: {"model": ErrorResponse, "description": "Validation error"},
        },
    )
    async def create_order(
        order: OrderRequest = Body(..., description="Order details"),
        user_id: Optional[UUID] = Cookie(None, description="User ID from cookie"),
        authorization: Optional[str] = Header(None, description="Authorization header"),
    ):
        """
        Create a new order with multiple items, shipping details, and payment information.
        Returns the created order with full details including status and tracking information.
        """
        # Return a copy of the example order response with the customer ID from the request
        order_copy = example_order_response.model_copy()
        order_copy.customer_id = order.customer_id
        order_copy.items = order.items
        return order_copy

    @app.get(
        "/customers/{customer_id}",
        response_model=Union[Customer, Dict[str, Any]],
        tags=["customers"],
        operation_id="get_customer",
        responses={
            404: {"model": ErrorResponse, "description": "Customer not found"},
            403: {"model": ErrorResponse, "description": "Forbidden access"},
        },
    )
    async def get_customer(
        customer_id: UUID = Path(..., description="The ID of the customer to retrieve"),
        include_orders: bool = Query(False, description="Include customer's order history"),
        include_payment_methods: bool = Query(False, description="Include customer's saved payment methods"),
        fields: List[str] = Query(None, description="Specific fields to include in response"),
    ):
        """
        Get detailed information about a specific customer by ID.
        Can include additional related information like order history.
        """
        # Return a copy of the example customer with the requested ID
        customer_copy = example_customer.model_copy()
        customer_copy.id = customer_id
        return customer_copy

    return app


@pytest.fixture
def complex_fastapi_app(
    example_product: Product,
    example_customer: Customer,
    example_order_response: OrderResponse,
) -> FastAPI:
    return make_complex_fastapi_app(
        example_product=example_product,
        example_customer=example_customer,
        example_order_response=example_order_response,
    )
