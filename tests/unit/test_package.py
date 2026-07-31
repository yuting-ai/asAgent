import asyncio

import ragent


def test_package_is_importable() -> None:
    assert ragent.__name__ == "ragent"


async def test_asyncio_support() -> None:
    await asyncio.sleep(0)
    assert asyncio.get_running_loop().is_running()
