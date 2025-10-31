# @Author: Bi Ying
# @Date:   2025-08-04
# FastAPI Server based on user's design

import time
from pathlib import Path
from threading import Thread, Event
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from utilities.general import mprint_with_name
from utilities.config import config

from api.workflow_api import (
    WorkflowAPI,
    WorkflowTagAPI,
    WorkflowTemplateAPI,
    WorkflowRunRecordAPI,
    WorkflowRunScheduleAPI,
)
from api.vector_database_api import DatabaseAPI, DatabaseObjectAPI

mprint = mprint_with_name(name="FastAPI Server")


class FastAPIServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.actual_port = None
        self.setup_fastapi_app()
        self.thread = None
        self.server_started_event = Event()

    def setup_fastapi_app(self):
        self.fastapi_app = FastAPI(title="VectorVein Backend API")

        # Add CORS middleware
        self.fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins for local API access
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add basic API endpoints
        @self.fastapi_app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": time.time(), "type": "desktop_api", "services": {"fastapi": "running", "celery": "running", "pywebview": "integrated"}}

        @self.fastapi_app.get("/api/info")
        async def api_info():
            return {
                "server_type": "local_desktop",
                "endpoints": {"workflow": "/api/workflow/*", "database": "/api/database/*", "health": "/health", "static": "/static/*", "assets": "/assets/*"},
                "task_queues": ["default", "qdrant"],
                "documentation": "/docs",
            }

        # Initialize API instances
        self.workflow_api = WorkflowAPI()
        self.workflow_tag_api = WorkflowTagAPI()
        self.workflow_template_api = WorkflowTemplateAPI()
        self.workflow_run_record_api = WorkflowRunRecordAPI()
        self.workflow_run_schedule_api = WorkflowRunScheduleAPI()
        self.database_api = DatabaseAPI()
        self.database_object_api = DatabaseObjectAPI()

        # Add Workflow API endpoints
        self.setup_workflow_endpoints()
        self.setup_database_endpoints()

        # Static files for user data
        data_static_path = Path(config.data_path) / "static"
        if data_static_path.exists():
            self.fastapi_app.mount("/static", StaticFiles(directory=data_static_path), name="static")

        # Static files for web assets (frontend resources)
        web_assets_path = Path(__file__).parent / "web" / "assets"
        if web_assets_path.exists():
            self.fastapi_app.mount("/assets", StaticFiles(directory=web_assets_path), name="web_assets")

        # Static files for web root (favicon, logo, etc.)
        web_root_path = Path(__file__).parent / "web"
        if web_root_path.exists():
            # Mount individual files from web root
            from fastapi.responses import FileResponse

            @self.fastapi_app.get("/")
            async def serve_index():
                """Serve the main index.html file"""
                index_path = web_root_path / "index.html"
                if index_path.exists():
                    return FileResponse(index_path, media_type="text/html")
                return {"error": "Index file not found"}

            @self.fastapi_app.get("/logo.svg")
            async def serve_logo():
                logo_path = web_root_path / "logo.svg"
                if logo_path.exists():
                    return FileResponse(logo_path)
                return {"error": "Logo not found"}

            @self.fastapi_app.get("/favicon.ico")
            async def serve_favicon():
                favicon_path = web_root_path / "favicon.ico"
                if favicon_path.exists():
                    return FileResponse(favicon_path)
                return {"error": "Favicon not found"}

    def setup_workflow_endpoints(self):
        """Setup workflow-related API endpoints"""

        # Request/Response Models
        class WorkflowRunRequest(BaseModel):
            wid: str  # Workflow ID
            output_scope: str = "output_fields_only"  # 'all' or 'output_fields_only'
            wait_for_completion: bool = False
            input_fields: Optional[list[Dict[str, Any]]] = []

        class CheckStatusRequest(BaseModel):
            rid: str  # Record ID

        class StandardResponse(BaseModel):
            status: int
            msg: str
            data: Any

        @self.fastapi_app.get("/api/workflow/list")
        async def list_workflows(
            page: int = 1,
            page_size: int = 20,
            search_text: Optional[str] = None,
            tags: Optional[str] = None,
        ):
            """List all workflows with pagination and filtering"""
            try:
                result = self.workflow_api.list({"page": page, "page_size": page_size, "search_text": search_text, "tags": tags.split(",") if tags else []})
                return result
            except Exception as e:
                mprint(f"Error listing workflows: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.fastapi_app.get("/api/workflow/{workflow_id}")
        async def get_workflow(workflow_id: str):
            """Get a specific workflow by ID"""
            try:
                result = self.workflow_api.get({"wid": workflow_id})
                if result.get("status") != 200:
                    raise HTTPException(status_code=404, detail="Workflow not found")
                return result["data"]
            except HTTPException:
                raise
            except Exception as e:
                mprint(f"Error getting workflow {workflow_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.fastapi_app.post("/api/workflow/run")
        async def run_workflow(request: WorkflowRunRequest):
            """Run a workflow with optional input data"""
            try:
                # Get the workflow first to validate it exists and get its data
                workflow_result = self.workflow_api.get({"wid": request.wid})
                if workflow_result.get("status") != 200:
                    return StandardResponse(status=404, msg="Workflow not found", data={})

                workflow = workflow_result["data"]
                workflow_data = workflow.get("data", {})  # This contains nodes, edges, etc.

                # Update the workflow data with input fields
                for field in request.input_fields or []:
                    node_id = field.get("node_id")
                    field_name = field.get("field_name")
                    value = field.get("value")
                    if node_id and workflow_data.get("nodes"):
                        # Find the node and update its field value
                        for node in workflow_data["nodes"]:
                            if node.get("id") == node_id:
                                if "data" not in node:
                                    node["data"] = {}
                                if "template" not in node["data"]:
                                    node["data"]["template"] = {}
                                if field_name not in node["data"]["template"]:
                                    node["data"]["template"][field_name] = {}
                                node["data"]["template"][field_name]["value"] = value
                                break

                # Run the workflow with the updated data
                run_result = self.workflow_api.run({"wid": request.wid, "data": workflow_data})

                if run_result.get("status") != 200:
                    return StandardResponse(status=run_result.get("status", 500), msg=run_result.get("msg", "Failed to run workflow"), data={})

                record_id = run_result["data"]["rid"]

                # If wait_for_completion is True, wait for the workflow to finish (max 30 seconds)
                if request.wait_for_completion:
                    import asyncio

                    max_wait_time = 30  # seconds
                    start_time = time.time()

                    while time.time() - start_time < max_wait_time:
                        record_result = self.workflow_run_record_api.get({"rid": record_id})
                        if record_result.get("status") != 200:
                            break
                        record_data = record_result["data"]
                        status = record_data.get("status", "RUNNING")

                        if status == "FINISHED":
                            # Get workflow output
                            output_data = record_data.get("data", {})
                            if request.output_scope == "output_fields_only":
                                # Filter to only output fields
                                output_data = self._filter_output_fields(output_data)

                            return StandardResponse(status=200, msg="FINISHED", data=output_data)
                        elif status == "FAILED":
                            error_info = record_data.get("error_message", "Workflow failed")
                            return StandardResponse(status=500, msg="FAILED", data={"error": error_info})

                        await asyncio.sleep(1)

                    # Timeout - return record ID
                    return StandardResponse(status=202, msg="TIMEOUT", data={"rid": record_id})
                else:
                    # Return immediately with record ID
                    return StandardResponse(status=200, msg="success", data={"rid": record_id})

            except Exception as e:
                mprint(f"Error running workflow: {e}")
                return StandardResponse(status=500, msg=str(e), data={})

        @self.fastapi_app.post("/api/workflow/check-status")
        async def check_workflow_status(request: CheckStatusRequest):
            """Check the status of a workflow run, including finished node updates for UI."""
            try:
                # Prefer fast cache path to provide incremental progress
                from utilities.config import cache as _cache

                finished_nodes = _cache.get(f"workflow:record:finished_nodes:{request.rid}", [])
                cached_status = _cache.get(f"workflow:record:{request.rid}")
                if cached_status == 202:
                    return StandardResponse(status=202, msg="RUNNING", data={"finished_nodes": finished_nodes})
                if cached_status == 404:
                    return StandardResponse(status=404, msg="Record not found", data={})

                # Fall back to DB lookup
                record_result = self.workflow_run_record_api.get({"rid": request.rid})
                if record_result.get("status") != 200:
                    # Cache 404 for a while to reduce DB pressure
                    _cache.set(f"workflow:record:{request.rid}", 404, 60 * 60)
                    return StandardResponse(status=404, msg="Record not found", data={})

                record = record_result["data"]
                status = record.get("status", "RUNNING")

                if status in ("RUNNING", "QUEUED"):
                    # Keep returning partial progress
                    return StandardResponse(status=202, msg=status, data={"finished_nodes": finished_nodes})
                elif status == "FINISHED":
                    # Format output data
                    output_data = self._format_workflow_output(record.get("data", {}))
                    _cache.set(f"workflow:record:{request.rid}", 200, 60 * 60)
                    return StandardResponse(status=200, msg="FINISHED", data=output_data)
                elif status == "FAILED":
                    error_info = record.get("error_message", "Unknown error")
                    error_task = record.get("error_task", "")
                    _cache.set(f"workflow:record:{request.rid}", 500, 60 * 60)
                    return StandardResponse(status=500, msg="FAILED", data={"error_task": error_task, "error": error_info})
                else:
                    return StandardResponse(status=500, msg=f"Unknown status: {status}", data={})

            except Exception as e:
                mprint(f"Error checking workflow status: {e}")
                return StandardResponse(status=500, msg=str(e), data={})

        @self.fastapi_app.get("/api/workflow/{workflow_id}/records")
        async def get_workflow_records(workflow_id: str, page: int = 1, page_size: int = 20):
            """Get run records for a specific workflow"""
            try:
                result = self.workflow_run_record_api.list({"wid": workflow_id, "page": page, "page_size": page_size})
                return result
            except Exception as e:
                mprint(f"Error getting workflow records {workflow_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.fastapi_app.post("/api/workflow/{workflow_id}/stop/{record_id}")
        async def stop_workflow(workflow_id: str, record_id: str):
            """Stop a running workflow"""
            try:
                # Note: The workflow API doesn't have a stop method, need to check this
                # For now, return a message that this feature is not yet implemented
                return {"workflow_id": workflow_id, "record_id": record_id, "status": "not_implemented", "message": "Stop workflow feature is not yet implemented"}
            except Exception as e:
                mprint(f"Error stopping workflow {workflow_id}/{record_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _filter_output_fields(self, data):
        """Filter workflow data to only include output fields"""
        try:
            # Import WorkflowData here to avoid circular imports
            from utilities.workflow import WorkflowData

            # Create WorkflowData instance and get output_contents
            workflow_data = WorkflowData(data)
            return workflow_data.output_contents
        except Exception as e:
            mprint(f"Error filtering output fields: {e}")
            # Fallback to returning all data if filtering fails
            return data

    def _format_workflow_output(self, data):
        """Format workflow output data into standard format"""
        try:
            # Import WorkflowData here to avoid circular imports
            from utilities.workflow import WorkflowData

            # Create WorkflowData instance and get output_contents
            workflow_data = WorkflowData(data)
            return workflow_data.output_contents
        except Exception as e:
            mprint(f"Error formatting workflow output: {e}")
            # Fallback to empty list if formatting fails
            return []

    def setup_database_endpoints(self):
        """Setup vector database API endpoints"""

        @self.fastapi_app.get("/api/database/list")
        async def list_databases(page: int = 1, page_size: int = 20):
            """List all vector databases"""
            try:
                result = self.database_api.list({"page": page, "page_size": page_size})
                return result
            except Exception as e:
                mprint(f"Error listing databases: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.fastapi_app.get("/api/database/{database_id}")
        async def get_database(database_id: str):
            """Get a specific database by ID"""
            try:
                result = self.database_api.get({"vid": database_id})
                if result.get("status") != 200:
                    raise HTTPException(status_code=404, detail="Database not found")
                return result["data"]
            except HTTPException:
                raise
            except Exception as e:
                mprint(f"Error getting database {database_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def find_free_port(self):
        """Find a free port for the server"""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def run_fastapi_server(self):
        """Run FastAPI server"""
        try:
            # Auto-assign port if requested
            if self.port == 0:
                self.actual_port = self.find_free_port()
            else:
                self.actual_port = self.port

            config = uvicorn.Config(
                self.fastapi_app,
                host=self.host,
                port=self.actual_port,
                log_level="warning",  # Reduce log noise for desktop app
            )
            server = uvicorn.Server(config)

            # Set up startup callback
            original_startup = server.startup

            async def new_startup(sockets=None):
                await original_startup(sockets)
                self.server_started_event.set()  # Signal that server has started

            server.startup = new_startup
            server.run()
        except Exception as e:
            mprint.error(f"FastAPI server failed to start: {e}")
            self.server_started_event.set()  # Set event to prevent infinite waiting

    def start(self):
        """Start FastAPI server in background thread"""
        self.thread = Thread(target=self._run_server, daemon=True)
        self.thread.start()

        # Wait for server to start
        self.server_started_event.wait(timeout=10)

        if self.server_started_event.is_set():
            mprint(f"FastAPI server started at http://{self.host}:{self.actual_port}")
            mprint(f"API Documentation: http://{self.host}:{self.actual_port}/docs")
        else:
            mprint.error("FastAPI server failed to start within timeout")

    def _run_server(self):
        """Internal method to run the server"""
        self.run_fastapi_server()

    def stop(self):
        """Stop FastAPI server"""
        self.server_started_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        mprint("FastAPI server stopped")
