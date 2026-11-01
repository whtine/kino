"""Minimal HTTP health endpoint for Render web services and uptime monitors."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def handle_health_request(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=5)
        parts = request_line.decode("ascii", errors="replace").strip().split()
        while await asyncio.wait_for(reader.readline(), timeout=5) not in (b"", b"\r\n"):
            pass

        if len(parts) != 3:
            status, body = "400 Bad Request", b"bad request\n"
        elif parts[0] not in {"GET", "HEAD"}:
            status, body = "405 Method Not Allowed", b"method not allowed\n"
        elif parts[1].split("?", 1)[0] in {"/", "/healthz", "/ping"}:
            status, body = "200 OK", b"ok\n"
        else:
            status, body = "404 Not Found", b"not found\n"

        response_body = b"" if parts and parts[0] == "HEAD" else body
        response = (
            f"HTTP/1.1 {status}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii") + response_body
        writer.write(response)
        await writer.drain()
    except asyncio.TimeoutError:
        logger.debug("Health check client timed out")
    except (ConnectionError, OSError):
        logger.debug("Health check client disconnected")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            logger.debug("Health check connection closed with an error")


async def start_health_server(port: int) -> asyncio.Server:
    return await asyncio.start_server(
        handle_health_request,
        host="0.0.0.0",
        port=port,
    )
