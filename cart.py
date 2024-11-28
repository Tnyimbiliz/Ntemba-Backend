from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import shortuuid  # Use shortuuid instead of ObjectId
from database import cart_collection, items_collection, order_collection
from user import get_current_active_user, UserInDB
from order import OrderItem, Order

# Pydantic models
class CartItem(BaseModel):
    item_id: str
    quantity: int

class Cart(BaseModel):
    user_id: str
    items: List[CartItem]

class CartItemInDB(CartItem):
    name: str
    description: str
    price: float

class CartInDB(BaseModel):
    id: str  # Cart ID will be the same as user_id
    user_id: str
    items: List[CartItemInDB]

class CartSummary(BaseModel):
    total_price: float
    total_items: int

router = APIRouter(
    prefix='/cart',
    tags=['cart']
)

# Add an item to the cart
@router.post("/add_item/", response_model=CartInDB)
async def add_item_to_cart(cart_item: CartItem, current_user: UserInDB = Depends(get_current_active_user)):
    item = items_collection.find_one({"id": cart_item.item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    cart = cart_collection.find_one({"user_id": current_user.id})
    if not cart:
        cart = {
            "id": current_user.id,  # Cart ID is the same as user ID
            "user_id": current_user.id,
            "items": []
        }
        cart_collection.insert_one(cart)
        cart = cart_collection.find_one({"user_id": current_user.id})

    existing_item = next((i for i in cart['items'] if i['item_id'] == cart_item.item_id), None)
    if existing_item:
        existing_item['quantity'] += cart_item.quantity
    else:
        cart['items'].append(cart_item.dict())

    cart_collection.update_one({"user_id": current_user.id}, {"$set": {"items": cart['items']}})

    # Retrieve updated cart with item details
    updated_cart = cart_collection.find_one({"user_id": current_user.id})
    detailed_items = []
    for item in updated_cart['items']:
        item_details = items_collection.find_one({"id": item['item_id']})
        if item_details:
            detailed_items.append(CartItemInDB(
                item_id=item['item_id'],
                quantity=item['quantity'],
                name=item_details['name'],
                description=item_details.get('description', ''),
                price=item_details['price']
            ))

    return CartInDB(id=updated_cart['id'], user_id=updated_cart['user_id'], items=detailed_items)

# Get all items in the cart
@router.get("/items/", response_model=List[CartItemInDB])
async def get_cart_items(current_user: UserInDB = Depends(get_current_active_user)):
    cart = cart_collection.find_one({"user_id": current_user.id})
    if not cart:
        return []

    detailed_items = []
    for item in cart['items']:
        item_details = items_collection.find_one({"id": item['item_id']})
        if item_details:
            detailed_items.append(CartItemInDB(
                item_id=item['item_id'],
                quantity=item['quantity'],
                name=item_details['name'],
                description=item_details.get('description', ''),
                price=item_details['price']
            ))

    return detailed_items

# Get cart details (total price and total items)
@router.get("/summary/", response_model=CartSummary)
async def get_cart_summary(current_user: UserInDB = Depends(get_current_active_user)):
    cart = cart_collection.find_one({"user_id": current_user.id})
    if not cart:
        return {"total_price": 0.0, "total_items": 0}

    total_price = 0.0
    total_items = 0
    for item in cart['items']:
        item_details = items_collection.find_one({"id": item['item_id']})
        if item_details:
            total_price += item_details['price'] * item['quantity']
            total_items += item['quantity']

    return {"total_price": total_price, "total_items": total_items}

# Remove an item from the cart
@router.delete("/remove_item/{item_id}", response_model=CartInDB)
async def remove_item_from_cart(item_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    cart = cart_collection.find_one({"user_id": current_user.id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    cart['items'] = [item for item in cart['items'] if item['item_id'] != item_id]

    cart_collection.update_one({"user_id": current_user.id}, {"$set": {"items": cart['items']}})

    # Retrieve updated cart with item details
    updated_cart = cart_collection.find_one({"user_id": current_user.id})
    detailed_items = []
    for item in updated_cart['items']:
        item_details = items_collection.find_one({"id": item['item_id']})
        if item_details:
            detailed_items.append(CartItemInDB(
                item_id=item['item_id'],
                quantity=item['quantity'],
                name=item_details['name'],
                description=item_details.get('description', ''),
                price=item_details['price']
            ))

    return CartInDB(id=updated_cart['id'], user_id=updated_cart['user_id'], items=detailed_items)

# Clear the cart (remove all items) (authentication required)
@router.delete("/clear_cart/")
async def clear_cart(current_user: UserInDB = Depends(get_current_active_user)):
    result = cart_collection.update_one({"user_id": current_user.id}, {"$set": {"items": []}})
    if result.modified_count:
        return {"message": "Cart cleared"}
    raise HTTPException(status_code=404, detail="Cart not found or already empty")

# Checkout order (create order from cart and clear the cart) (authentication required)
@router.post("/checkout_order/", response_model=Order)
async def checkout_order(current_user: UserInDB = Depends(get_current_active_user)):
    cart = cart_collection.find_one({"user_id": current_user.id})
    if not cart or not cart['items']:
        raise HTTPException(status_code=404, detail="Cart is empty")

    items = []
    total_price = 0.0
    store_ids = set()  # Set to store unique store IDs
    generated_confirmation_code = f"{shortuuid.ShortUUID().random(length=3)}"

    for cart_item in cart['items']:
        item_details = items_collection.find_one({"id": cart_item['item_id']})
        if not item_details:
            continue
        
        total_price += item_details['price'] * cart_item['quantity']
        items.append(OrderItem(
            item_id=cart_item['item_id'],
            name=item_details['name'],
            description=item_details.get('description', ''),
            price=item_details['price'],
            quantity=cart_item['quantity'],
            confirmation_code=generated_confirmation_code
        ))

        # Add store_id to the set of store_ids
        store_ids.add(item_details['store_id'])

    # Generate a unique order ID
    order_id = shortuuid.uuid()

    order_data = {
        "id": order_id,  # Set the generated order ID here
        "user_id": current_user.id,
        "items": [item.dict() for item in items],
        "total_price": total_price,
        "status": "Pending",
        "confirmation_code": generated_confirmation_code,
        "store_ids": list(store_ids),  # Include the list of unique store IDs in the order data
        "rider_ids": None
    }
    
    result = order_collection.insert_one(order_data)
    order = order_collection.find_one({"id": order_id})

    # Clear the cart after creating the order
    cart_collection.update_one({"user_id": current_user.id}, {"$set": {"items": []}})

    return Order(
        id=str(order['id']),
        user_id=order['user_id'],
        items=[OrderItem(**item) for item in order['items']],
        total_price=order['total_price'],
        status=order['status'],
        confirmation_code=order['items'][0]['confirmation_code'],  # Assuming all items have the same confirmation code
        store_ids=order.get('store_ids', [])  # Retrieve store_ids from the order data
    )


