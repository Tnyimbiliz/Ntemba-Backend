from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from starlette.requests import Request


#from other files
import item, user, cart, order, store, register, store_ratings

# Create FastAPI instance
app = FastAPI()

app.include_router(user.router)
app.include_router(item.router)
app.include_router(cart.router)
app.include_router(order.router)
app.include_router(store.router)
app.include_router(register.router)
app.include_router(store_ratings.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def ping(request:Request):
    return {"data":"pinged successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


#FIX THE URL FRONT ENDPOINT PROBLEM