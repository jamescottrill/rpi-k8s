"""
CronJob entry point. Invokes handler.handle() once and exits with a non-zero
status if the handler reports failure, so the Job records as Failed and shows
up in `kubectl get jobs`.
"""

import json
import sys

from handler import handle


def main() -> int:
    result = handle(event=None, context=None)
    if isinstance(result, dict):
        body = result.get("body", "")
        status = result.get("statusCode", 200)
        if status >= 400:
            print(f"handler reported failure (status={status}): {body}", file=sys.stderr)
            return 1
        print(f"handler ok (status={status}): {body}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
