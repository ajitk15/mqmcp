from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import uvicorn
import os
import sys

# Add the current directory to sys.path so we can import mqmcpserver1
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mqmcpserver1 import dspmq, dspmqver, runmqsc

app = FastAPI(title="IBM MQ MCP API", description="REST API to interact with IBM MQ using MCP tools")

class MQSCRequest(BaseModel):
    qmgr_name: str
    mqsc_command: str

@app.get("/dspmq")
async def get_dspmq():
    """List available queue managers and whether they are running or not."""
    try:
        return {"result": await dspmq()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dspmqver")
async def get_dspmqver():
    """Display IBM MQ version and installation information."""
    try:
        return {"result": await dspmqver()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/runmqsc")
async def post_runmqsc(request: MQSCRequest):
    """Run an MQSC command against a specific queue manager."""
    try:
        return {"result": await runmqsc(request.qmgr_name, request.mqsc_command)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
