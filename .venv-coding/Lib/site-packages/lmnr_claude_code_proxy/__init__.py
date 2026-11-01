"""
Laminar Claude Code Proxy - Python bindings for HTTP proxy server
"""

import httpx
import logging
import threading
import time
from .lmnr_claude_code_proxy import run, stop_with_timeout

logger = logging.getLogger(__name__)

__all__ = ["ProxyServer", "run_server", "stop_server", "set_current_trace"]

HEALTH_CHECK_INTERVAL = 1
DEFAULT_TIMEOUT = 4


class ProxyServer:
    """
    A Claude Code Proxy server instance that can be run on a specific port.

    Each instance manages its own server state, health monitoring thread,
    and can be started/stopped independently.

    Example:
        # Create multiple proxy instances on different ports
        proxy1 = ProxyServer(port=45667)
        proxy2 = ProxyServer(port=45668)

        proxy1.run_server("https://api.anthropic.com")
        proxy2.run_server("https://api.anthropic.com")

        proxy1.set_current_trace(trace_id="...", span_id="...", project_api_key="...")
        proxy2.set_current_trace(trace_id="...", span_id="...", project_api_key="...")

        proxy1.stop_server()
        proxy2.stop_server()
    """

    def __init__(self, port: int = 45667):
        """
        Initialize a new proxy server instance.

        Args:
            port: The port to listen on (default: 45667)
        """
        self.port = port
        self._target_url: str = ""
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitoring = threading.Event()
        self._is_running = False

    def set_current_trace(
        self,
        trace_id: str,
        span_id: str,
        project_api_key: str,
        span_ids_path: list[str] | None = None,
        span_path: list[str] | None = None,
        laminar_url: str = "https://api.lmnr.ai",
    ) -> None:
        """
        Set the current trace context by sending an HTTP request to this proxy server.

        Args:
            trace_id: The trace ID
            span_id: The span ID
            project_api_key: The project API key
            span_ids_path: List of span IDs in the path
            span_path: List of span names in the path
            laminar_url: The Laminar API URL

        Raises:
            httpx.HTTPError: If the HTTP request fails.
        """
        # Prepare the JSON payload
        payload = {
            "trace_id": trace_id,
            "span_id": span_id,
            "project_api_key": project_api_key,
            "span_ids_path": span_ids_path or [],
            "span_path": span_path or [],
            "laminar_url": laminar_url,
        }

        # Send POST request to the internal endpoint
        url = f"http://127.0.0.1:{self.port}/lmnr-internal/span-context"

        with httpx.Client() as client:
            response = client.post(url, json=payload, timeout=5.0)
            response.raise_for_status()

    def _health_check_monitor(self) -> None:
        """
        Background thread that monitors server health and restarts if needed.
        Polls every HEALTH_CHECK_INTERVAL seconds.
        """
        while not self._stop_monitoring.is_set():
            # Wait for HEALTH_CHECK_INTERVAL seconds, but check stop flag more frequently
            if self._stop_monitoring.wait(timeout=HEALTH_CHECK_INTERVAL):
                break

            # Try to check server health
            try:
                url = f"http://127.0.0.1:{self.port}/lmnr-internal/health"
                with httpx.Client() as client:
                    response = client.get(url, timeout=2.0)
                    if response.status_code == 200:
                        # Server is healthy
                        continue
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as e:
                # Server is not responding, try to restart
                logger.warning(
                    "Server health check failed on port %d: %s. Attempting to restart...",
                    self.port,
                    e
                )
                try:
                    # Try to stop the existing server (it might be stuck)
                    try:
                        stop_with_timeout(self.port, DEFAULT_TIMEOUT)
                    except Exception:
                        pass  # Server might already be dead

                    # Wait a bit before restarting
                    time.sleep(0.1)

                    # Restart the server
                    run(self._target_url, self.port)
                    logger.info("Server restarted successfully on port %d", self.port)
                except Exception as restart_error:
                    logger.error(
                        "Failed to restart server on port %d: %s",
                        self.port,
                        restart_error
                    )

    def run_server(self, target_url: str) -> None:
        """
        Run the proxy server in a background thread with health monitoring.

        A background monitor thread will check the server health every
        HEALTH_CHECK_INTERVAL seconds and automatically restart it if it dies.

        Args:
            target_url: The target URL to proxy requests to
        """
        # Stop any existing monitoring
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._stop_monitoring.set()
            self._monitor_thread.join(timeout=HEALTH_CHECK_INTERVAL + 1)

        # Reset the stop flag
        self._stop_monitoring.clear()

        # Store server configuration
        self._target_url = target_url

        # Start the server
        try:
            run(target_url, self.port)
            self._is_running = True
        except Exception as e:
            logger.error("Error running the proxy server on port %d: %s", self.port, e)
            raise

        # Start the health check monitor thread
        self._monitor_thread = threading.Thread(
            target=self._health_check_monitor,
            daemon=True,
            name=f"proxy-monitor-{self.port}"
        )
        self._monitor_thread.start()

    def stop_server(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """
        Stop the proxy server and its health monitoring thread.

        Args:
            timeout: Maximum time in seconds to wait for graceful shutdown (default: 4).
                     The server will abort pending connections and background tasks after timeout/2.
        """
        # Signal the monitor thread to stop
        self._stop_monitoring.set()

        # Once we stop monitoring, we've lost active management of the server,
        # so we mark it as not running regardless of shutdown success
        self._is_running = False

        # Stop the server
        try:
            stop_with_timeout(self.port, timeout)
        except Exception as e:
            logger.debug("Error stopping the proxy server on port %d: %s", self.port, e)
            # Re-raise to inform caller of the issue
            raise
        finally:
            # Wait for monitor thread to finish
            if self._monitor_thread is not None:
                self._monitor_thread.join(timeout=2.0)
                self._monitor_thread = None

        logger.debug("Stopped proxy server and health monitoring on port %d", self.port)

    @property
    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self._is_running


# Singleton instance for backwards compatibility
_global_proxy: ProxyServer | None = None


def _get_global_proxy(port: int = 45667) -> ProxyServer:
    """Get or create the global singleton proxy instance."""
    global _global_proxy
    if _global_proxy is None:
        _global_proxy = ProxyServer(port=port)
    return _global_proxy


def run_server(target_url: str, port: int = 45667) -> None:
    """
    Run the proxy server in a background thread with health monitoring.

    This is a backwards-compatible function that uses a global singleton instance.
    For more control, consider creating your own ProxyServer instance.

    A background monitor thread will check the server health every
    HEALTH_CHECK_INTERVAL seconds and automatically restart it if it dies.

    Args:
        target_url: The target URL to proxy requests to
        port: The port to listen on (default: 45667)
    """
    global _global_proxy

    # If port is different from current global instance, create a new one
    proxy = _get_global_proxy(port)
    if proxy.port != port:
        # Stop old instance if running
        if proxy.is_running:
            proxy.stop_server()
        # Create new instance with the requested port
        _global_proxy = ProxyServer(port=port)
        proxy = _global_proxy

    proxy.run_server(target_url)


def stop_server(timeout: int = DEFAULT_TIMEOUT) -> None:
    """
    Stop the proxy server and its health monitoring thread.

    This is a backwards-compatible function that uses a global singleton instance.
    For more control, consider creating your own ProxyServer instance.

    Args:
        timeout: Maximum time in seconds to wait for graceful shutdown (default: 4).
                 The server will abort pending connections and background tasks after timeout/2.
    """
    proxy = _get_global_proxy()
    proxy.stop_server(timeout=timeout)


def set_current_trace(
    trace_id: str,
    span_id: str,
    project_api_key: str,
    span_ids_path: list[str] | None = None,
    span_path: list[str] | None = None,
    laminar_url: str = "https://api.lmnr.ai",
) -> None:
    """
    Set the current trace context by sending an HTTP request to the running proxy server.

    This is a backwards-compatible function that uses a global singleton instance.
    For more control, consider creating your own ProxyServer instance.

    Args:
        trace_id: The trace ID
        span_id: The span ID
        project_api_key: The project API key
        span_ids_path: List of span IDs in the path
        span_path: List of span names in the path
        laminar_url: The Laminar API URL

    Raises:
        httpx.HTTPError: If the HTTP request fails.
    """
    proxy = _get_global_proxy()
    proxy.set_current_trace(
        trace_id=trace_id,
        span_id=span_id,
        project_api_key=project_api_key,
        span_ids_path=span_ids_path,
        span_path=span_path,
        laminar_url=laminar_url,
    )

