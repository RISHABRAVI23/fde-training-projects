import asyncio
import time

import httpx

sem = asyncio.Semaphore(10)

active_count = 0
max_count = 0


async def fetch(client: httpx.AsyncClient, url: str) -> dict[str, object]:
    global active_count, max_count
    async with sem:
        active_count += 1
        max_count = max(max_count, active_count)
        start = time.perf_counter()
        try:
            response = await client.get(url)
            return {
                "url": url,
                "status": response.status_code,
                "time_elapsed": time.perf_counter() - start,
            }

        except httpx.HTTPError as e:
            return {
                "url": url,
                "error": repr(e),
                "time_elapsed": time.perf_counter() - start,
            }
        finally:
            active_count -= 1


async def main() -> None:
    urls = [f"http://localhost:8000/page{i}" for i in range(50)]
    start = time.perf_counter()

    async with httpx.AsyncClient(timeout=10.0) as client:
        results = await asyncio.gather(*[fetch(client, url) for url in urls])

    for result in results:
        print(result)
    print(f"total time: {time.perf_counter() - start:.2f}")
    print(f"max in flight: {max_count}")


if __name__ == "__main__":
    asyncio.run(main())
