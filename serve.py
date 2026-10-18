#!/usr/bin/env python3
# ABOUTME: Serves the CADScope viewer from this checkout for local development.
# ABOUTME: Like `python3 -m http.server`, but keeps up with the viewer's burst of module requests.
"""Usage: python3 serve.py [port]    (port 8000 by default)

Then open http://127.0.0.1:<port>/ in a browser.
"""

import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


class Server(http.server.ThreadingHTTPServer):
    # The viewer requests all of its ES modules at once. With the stock
    # backlog of 5 the OS resets the overflow connections, and one failed
    # module import stops the viewer from loading.
    request_queue_size = 128


def make_server(port):
    """A server for this checkout on 127.0.0.1:port; port 0 picks a free one."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    return Server(("127.0.0.1", port), handler)


def main():
    server = make_server(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
    print(f"Serving {ROOT} at http://127.0.0.1:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
