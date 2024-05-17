import requests
from datetime import datetime, time, timedelta
import json
import re
from typing import Annotated, List, Optional
from fastapi import Body, FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, Field, TypeAdapter
import motor.motor_asyncio
from dotenv import dotenv_values
from bson import ObjectId
from pymongo import ReturnDocument
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

config = dotenv_values(".env")

client = motor.motor_asyncio.AsyncIOMotorClient(config["MONGO_URL"])
db = client.tank_man

app = FastAPI()

format = "%Y-%m-%d %H:%M:%S %Z%z"

origins = ["http://localhost:8000", 
           "https://simple-smart-hub-client.netlify.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PyObjectId = Annotated[str, BeforeValidator(str)]

class Settings(BaseModel):
    id: Optional[PyObjectId] = Field(alias = "_id", default = None)
    user_temp: Optional[float] = None
    user_light: Optional[str] = None
    light_time_off: Optional[str] = None
    light_duration: Optional[str] = None

class updatedSettings(BaseModel):
    id: Optional[PyObjectId] = Field(alias = "_id", default = None)
    user_temp: Optional[float] = None
    user_light: Optional[str] = None
    light_time_off: Optional[str] = None

class sensorData(BaseModel):
    id: Optional[PyObjectId] = Field(alias = "_id", default = None)
    temperature: Optional[float] = None
    presence: Optional[bool] = None
    datetime: Optional[str] = None

regex = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')

def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)

 
def convert24(time):
    # Parse the time string into a datetime object
    t = datetime.strptime(time, '%I:%M:%S %p')
    # Format the datetime object into a 24-hour time string
    return t.strftime('%H:%M:%S')

def sunset_calculation():
    URL = "https://api.sunrisesunset.io/json"
    PARAMS = {"lat":"17.97787",
                "lng": "-76.77339"}
    r = requests.get(url=URL, params=PARAMS)
    response = r.json()
    sunset_time = response["results"]["sunset"]
    sunset_24 = convert24(sunset_time)
    return sunset_24

# get request to collect environmental data from ESP
@app.get("/graph")
async def get_data(size: int = None):
    data = await db["data"].find().to_list(size)
    return TypeAdapter(List[sensorData]).validate_python(data)

# to post fake data to test get
# @app.post("/graph", status_code=201)
# async def create_data(data: graph):
#     new_entry = await db["data"].insert_one(data.model_dump())
#     created_entry = await db["data"].find_one({"_id": new_entry.inserted_id})

#     return graph(**created_entry)

@app.put("/settings", status_code=200)
async def update_settings(settings_update: Settings = Body(...)):
    if settings_update.user_light == "sunset":
        user_light = datetime.strptime(sunset_calculation(), "%H:%M:%S")
    else:
        user_light = datetime.strptime(settings_update.user_light, "%H:%M:%S")

    duration = parse_time(settings_update.light_duration)
    settings_update.light_time_off = (user_light + duration).strftime("%H:%M:%S")
    all_settings = await db["settings"].find().to_list(999)
    if len(all_settings)==1:
        db["settings"].update_one({"_id":all_settings[0]["_id"]},{"$set":settings_update.model_dump(exclude = ["light_duration"])})
        updated_settings = await db["settings"].find_one({"_id": all_settings[0]["_id"]})
        return updatedSettings(**updated_settings)
    
    else:
        new_settings = await db["settings"].insert_one(settings_update.model_dump(exclude = ["light_duration"]))
        created_settings = await db["settings"].find_one({"_id": new_settings.inserted_id})
        final = (updatedSettings(**created_settings)).model_dump()
        # raise HTTPException(status_code=201)
        return JSONResponse(status_code=201, content=final)
    
@app.post("/sensorData",status_code=201)
async def createSensorData(sensor_data:sensorData):
    new_data = await db["sensorData"].insert_one(sensor_data.model_dump())
    created_data = await db["sensorData"].find_one({"_id": new_data.inserted_id})
    return sensorData(**created_data)

@app.get("/sensorData", status_code=200)
async def get_device_states():
    data = await db["sensorData"].find().to_list(999)
    num = len(data) - 1
    sensor = data[num]

    all_settings = await db["settings"].find().to_list(999)
    user_pref = all_settings[0]

    components = {
        "fan": False,
        "light": False
    }

    if ((sensor["temperature"] == user_pref["user_temp"]) & (sensor["presence"] == True) ):
        components["fan"] = True
    else:
        components["fan"] = False
    
    if ((sensor["datetime"] == user_pref["user_light"]) & (sensor["presence"] == True) ):
        components["light"] = True
    else:
        components["light"] = False
    
    return components