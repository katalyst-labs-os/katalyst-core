from PIL import Image
from lancedb.pydantic import LanceModel
import urllib.parse


class Design(LanceModel):
    name: str
    description: str
    image_uri: str
    code: str
    vector: list[float]

    @property
    def image(self):
        return Image.open(urllib.parse.urlparse(self.image_uri).path)
