from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import shortuuid
from typing import List, Dict
from bson import ObjectId
from random import randint
from database import order_collection, cart_collection, items_collection, store_collection
from user import get_current_active_user, UserInDB

# Pydantic models
class OrderItem(BaseModel):
    item_id: str
    name: str
    description: str
    price: float
    quantity: int
    confirmation_code: str

class Order(BaseModel):
    id: str
    user_id: str
    items: List[OrderItem]
    total_price: float
    status: str  # Example status: 'Pending', 'Completed', 'Cancelled'
    confirmation_code: str  # New field for the confirmation code
    store_ids: List[str]  # Add this line

class OrderInDB(Order):
    id: str = Field(default_factory=shortuuid.uuid)
    store_id: str

# Define a new model for the get_orders endpoint
class OrderSummary(BaseModel):
    id: str
    total_price: int
    status: str
    confirmation_code: str
    items: List[Dict[str, str]]

router = APIRouter(
    prefix='/order',
    tags=['order']
)

# Get all orders for the current user with only item IDs and names
@router.get("/", response_model=List[OrderSummary])
async def get_orders(current_user: UserInDB = Depends(get_current_active_user)):
    orders = order_collection.find({"user_id": current_user.id})
    if not orders:
        raise HTTPException(status_code=404, detail="No orders found for the user")

    result = []
    for order in orders:
        order_info = OrderSummary(
            id=order['id'],
            total_price = order['total_price'],
            status = order['status'],
            confirmation_code = order['confirmation_code'],
            items=[{"item_id": item['item_id'], "name": item['name']} for item in order['items']]
        )
        result.append(order_info)

    return result

# Get all orders for the current user's store with only item IDs and names 
@router.get("/customer_orders/", response_model=List[OrderSummary])
async def get_customer_orders(current_user: UserInDB = Depends(get_current_active_user)):
    # Step 1: Find the store that belongs to the current user
    store = store_collection.find_one({"user_id": current_user.id})  # Use find_one to get a single document
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found for the current user")

    # Step 2: Find orders where the current user's store ID is in the store_ids field
    orders = order_collection.find({"store_ids": store["id"]})

    result = []
    # Convert cursor to list for synchronous iteration
    orders_list = list(orders)  # Remove await

    for order in orders_list:
        # Filter items to include only those that belong to the current user's store
        filtered_items = [
            {"item_id": item['item_id'], "name": item['name']}
            for item in order['items']
            # You can also filter items here if needed
        ]

        if filtered_items:  # Only add orders with relevant items
            order_info = OrderSummary(
                id=order['id'],
                total_price=order['total_price'],
                status=order['status'],
                confirmation_code=order['confirmation_code'],
                items=filtered_items
            )
            result.append(order_info)

    if not result:
        return []

    return result

# Get all orders for the rider that have been confirmed
@router.get("/riders_orders/", response_model=List[OrderSummary])
async def get_riders_orders(current_user: UserInDB = Depends(get_current_active_user)):
    # Step 2: Find orders where the current user's store ID is in the store_ids field
    orders = order_collection.find({"status": "Confirmed"})

    result = []
    # Convert cursor to list for synchronous iteration
    orders_list = list(orders)  # Remove await

    for order in orders_list:
        # Filter items to include only those that belong to the current user's store
        filtered_items = [
            {"item_id": item['item_id'], "name": item['name']}
            for item in order['items']
            # You can also filter items here if needed
        ]

        if filtered_items:  # Only add orders with relevant items
            order_info = OrderSummary(
                id=order['id'],
                total_price=order['total_price'],
                status=order['status'],
                confirmation_code=order['confirmation_code'],
                items=filtered_items
            )
            result.append(order_info)

    if not result:
        raise HTTPException(status_code=404, detail="No orders found for the user's store")

    return result


@router.put("/complete/")
async def complete_order(order_id: str, confirmation_code: str, current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.type != 1 and current_user.type != 2:  # Check if user is an admin
        raise HTTPException(status_code=403, detail="Not authorized to complete the order")

    order = order_collection.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order['status'] == 'Completed':
        raise HTTPException(status_code=400, detail="Order already completed")

    # Validate the confirmation code
    if order['confirmation_code'] != confirmation_code:
        raise HTTPException(status_code=400, detail="Invalid confirmation code")

    order_collection.update_one({"id": order_id}, {"$set": {"status": "Completed"}})
    updated_order = order_collection.find_one({"id": order_id})
    return {"message": "Order Completed successfully"}


# Get all items in an order
@router.get("/{order_id}/items/", response_model=List[OrderItem])
async def get_order_items(order_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    order = order_collection.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return [OrderItem(**item) for item in order['items']]

# Get order summary (total price and total items)
@router.get("/{order_id}/summary/", response_model=dict)
async def get_order_summary(order_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    order = order_collection.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    total_price = sum(item['price'] * item['quantity'] for item in order['items'])
    total_items = sum(item['quantity'] for item in order['items'])

    return {"total_price": total_price, "total_items": total_items}

# Cancel the order (by either admin or order owner)
@router.put("/cancel/{order_id}")
async def cancel_order(order_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    # Check if user is an admin or the order owner
    order = order_collection.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order['user_id'] != current_user.id and current_user.type != 1:  # Check if user is not the owner and not an admin
        raise HTTPException(status_code=403, detail="Not authorized to cancel the order")
    
    if order['status'] == 'Cancelled':
        raise HTTPException(status_code=400, detail="Order already cancelled")
    
    if order['status'] != 'Pending':
        raise HTTPException(status_code=400, detail="Order is already being processed!")
    
    order_collection.update_one({"id": order_id}, {"$set": {"status": "Cancelled"}})
    return {"message": "Order cancelled successfully"}

# Confirm the order (by either admin or store owner associated with the order)
@router.put("/confirm/{order_id}")
async def confirm_order(order_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    # Step 1: Find the order
    order = order_collection.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Step 2: Find the store for the current user
    store = store_collection.find_one({"user_id": current_user.id})

    if not store:
        raise HTTPException(status_code=404, detail="Store not found for the current user")
    
    # Check if the current user's store is part of the store_ids for that order
    if store["id"] not in order['store_ids']:
        raise HTTPException(status_code=403, detail="Not authorized to confirm this order")

    # Step 3: Check order status
    if order['status'] == 'Confirmed':
        raise HTTPException(status_code=400, detail="Order already confirmed")
    
    # Step 4: Update the order status to Confirmed
    order_collection.update_one({"id": order_id}, {"$set": {"status": "Confirmed"}})
    
    return {"message": "Order confirmed successfully"}


# Create a new order from the cart (authentication required)
@router.post("/create_from_cart/", response_model=Order)
async def create_order_from_cart(current_user: UserInDB = Depends(get_current_active_user)):
    cart = cart_collection.find_one({"user_id": current_user.id})
    if not cart or not cart['items']:
        raise HTTPException(status_code=404, detail="Cart is empty")

    items = []
    total_price = 0.0
    for cart_item in cart['items']:
        item_details = items_collection.find_one({"_id": ObjectId(cart_item['item_id'])})
        if not item_details:
            continue
        total_price += item_details['price'] * cart_item['quantity']
        items.append(OrderItem(
            item_id=cart_item['item_id'],
            name=item_details['name'],
            description=item_details.get('description', ''),
            price=item_details['price'],
            quantity=cart_item['quantity']
        ))

    # Generate a random 3-digit confirmation code
    confirmation_code = randint(100, 999)

    order_data = {
        "user_id": current_user.id,
        "items": [item.dict() for item in items],
        "total_price": total_price,
        "status": "Pending",
        "confirmation_code": confirmation_code  # Store the confirmation code
    }
    result = order_collection.insert_one(order_data)
    order = order_collection.find_one({"_id": result.inserted_id})
    
    # Clear the cart after creating the order
    cart_collection.update_one({"user_id": current_user.id}, {"$set": {"items": []}})

    return Order(
        id=str(order['_id']),
        user_id=order['user_id'],
        items=[OrderItem(**item) for item in order['items']],
        total_price=order['total_price'],
        status=order['status'],
        confirmation_code=order['confirmation_code']  # Return the confirmation code in the response
    )


@router.get("/order_details/{order_id}", response_model=dict)
async def get_order_details(order_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    order = order_collection.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order_details = {
        "total_price": order['total_price'],
        "confirmation_code": order['confirmation_code'],
        "status": order["status"],
        "items": [{"name": item['name'], "price": item['price']} for item in order['items']],
        "store_ids": [{"id": id} for id in order['store_ids']]
    }

    return order_details