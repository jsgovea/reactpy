import asyncio
import pytest

import idom
from idom.core.layout import Layout, RenderError, LayoutEvent
from idom.core.render import SingleStateRenderer, SharedStateRenderer, StopRendering


async def test_render_error_without_partial_render_raises():
    class LayoutWithBadRenderError(Layout):
        async def render(self):
            raise RenderError("no partial render")

    @idom.element
    async def pass_element(self):
        return idom.html.div()

    bad_layout = LayoutWithBadRenderError(pass_element())
    renderer = SingleStateRenderer(bad_layout)

    async def send(data):
        raise StopRendering()

    async def recv():
        raise StopRendering()

    with pytest.raises(RenderError, match="no partial render"):
        await renderer.run(send, recv, None)


async def test_shared_state_renderer():
    done = asyncio.Event()
    data_sent_1 = asyncio.Queue()
    data_sent_2 = []

    async def send_1(data):
        await data_sent_1.put(data)

    async def recv_1():
        sent = await data_sent_1.get()

        element_id = sent["root"]
        element_data = sent["new"][element_id]

        if element_data["attributes"]["count"] == 4:
            done.set()
            raise StopRendering()

        target = element_data["eventHandlers"]["anEvent"]["target"]
        return LayoutEvent(target=target, data=[])

    async def send_2(data):
        element_id = data["root"]
        element_data = data["new"][element_id]
        data_sent_2.append(element_data["attributes"]["count"])

    async def recv_2():
        await done.wait()
        raise StopRendering()

    @idom.element
    async def Clickable(self, count=0):
        @idom.event
        async def an_event():
            self.update(count=count + 1)

        return idom.html.div({"anEvent": an_event, "count": count})

    async with SharedStateRenderer(Layout(Clickable())) as renderer:
        await renderer.run(send_1, recv_1, "1")
        await renderer.run(send_2, recv_2, "2")

    # There's an extra 0 here since the render has to be sure that all
    # views get the current model state the first time they connect.
    assert data_sent_2 == [0, 0, 1, 2, 3, 4]
