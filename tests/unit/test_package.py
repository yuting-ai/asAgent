import asyncio

import asagent


def test_package_is_importable() -> None:
    assert asagent.__name__ == "asagent"


async def test_asyncio_support() -> None:
    await asyncio.sleep(0)
    assert asyncio.get_running_loop().is_running()
