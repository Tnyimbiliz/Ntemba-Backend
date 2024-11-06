from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from starlette.requests import Request

# to run 
# uvicorn main:app --reload


#from other files
import item, user, cart, order, store

# Create FastAPI instance
app = FastAPI()

# Mount the 'images' directory for static file access
app.mount("/images", StaticFiles(directory="images"), name="images")

app.include_router(user.router)
app.include_router(item.router)
app.include_router(cart.router)
app.include_router(order.router)
app.include_router(store.router)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Update `origins` to include localhost and your frontend's production URL
origins = [
    "http://localhost:3000",   # React local dev server, if applicable
    "http://localhost:8000",   # Your current local frontend server
    "https://www.ntembaz.com",     # Your production frontend domain
    "https://ntembaz.com",    
    "https://www.ntembaz.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Allow specified origins
    allow_credentials=True,      # Allow credentials if needed (e.g., cookies)
    allow_methods=["*"],         # Allow all HTTP methods
    allow_headers=["*"],         # Allow all headers
)

templates = Jinja2Templates(directory="templates")

# Endpoint to serve the login page
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Endpoint to serve the signup page
@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

# Endpoint to serve the signup page
@app.get("/create_store", response_class=HTMLResponse)
async def create_store_page(request: Request):
    return templates.TemplateResponse("createstore.html", {"request": request})

@app.get("/get_store/{store_id}", response_class=HTMLResponse)
async def get_item_details_page(request: Request, store_id: str):
    return templates.TemplateResponse("getstore.html", {"request": request, "store_id": store_id})

# Endpoint to serve the signup page
@app.get("/role", response_class=HTMLResponse)
async def role_page(request: Request):
    return templates.TemplateResponse("role.html", {"request": request})


# Endpoint to serve the signup page
@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})

# Endpoint to serve the items page
@app.get("/items", response_class=HTMLResponse)
async def get_items_page(request: Request):
    return templates.TemplateResponse("getitems.html", {"request": request})

# Endpoint to serve the items page
@app.get("/my_items", response_class=HTMLResponse)
async def get_my_items_page(request: Request):
    return templates.TemplateResponse("getitemsbyme.html", {"request": request})

# Endpoint to serve the items page
@app.get("/add_item", response_class=HTMLResponse)
async def get_add_items_page(request: Request):
    return templates.TemplateResponse("additem.html", {"request": request})

@app.get("/item-details/{item_id}", response_class=HTMLResponse)
async def get_item_details_page(request: Request, item_id: str):
    return templates.TemplateResponse("itemdetails.html", {"request": request, "item_id": item_id}
                                      )
# Endpoint to serve the search page
@app.get("/search/{phrase}", response_class=HTMLResponse)
async def signup_page(request: Request, phrase: str):
    return templates.TemplateResponse("search.html", {"request": request, "phrase": phrase})

# Endpoint to serve the search all page
@app.get("/search_all", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("searchall.html", {"request": request})

# Endpoint to serve the register a rider
@app.get("/register_rider", response_class=HTMLResponse)
async def register_rider_page(request: Request):
    return templates.TemplateResponse("registerrider.html", {"request": request})

# Endpoint to serve the items page
@app.get("/cart", response_class=HTMLResponse)
async def get_cart_page(request: Request):
    return templates.TemplateResponse("cart.html", {"request": request})

@app.get("/orders", response_class=HTMLResponse)
async def get_orders_page(request: Request):
    return templates.TemplateResponse("orders.html", {"request": request})

@app.get("/order_details/{order_id}", response_class= HTMLResponse)
async def get_order_details_page(request: Request, order_id: str):
    return templates.TemplateResponse("orderdetails.html", {"request": request, "order_id": order_id})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


#FIX THE URL FRONT ENDPOINT PROBLEM