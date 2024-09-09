import pandas as pd
from PIL import Image
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import EmbeddingFunctionRegistry
import os

VECDB_PATH = "storage/dataset/multimodal_vector_db"
DATASET_PATH = "storage/dataset/dataset.csv"
PICTURES_PATH = "storage/dataset/files/"


registry = EmbeddingFunctionRegistry.get_instance()
clip = registry.get("open-clip").create(
    name="hf-hub:apple/MobileCLIP-B-LT-OpenCLIP", pretrained=""
)


class Design(LanceModel):
    name: str
    description: str
    image_uri: str = clip.SourceField()
    backend: str
    code: str
    vector: Vector(clip.ndims()) = clip.VectorField()  # type: ignore

    @property
    def images(self):
        return Image.open(self.image_uri)


images_path = PICTURES_PATH

df = pd.read_csv(DATASET_PATH)
df = df[df["files"].notna()]
df = df[df["files"] != ""]
df = df.assign(files=df["files"].str.split(";")).explode("files").reset_index(drop=True)

df = df[df["files"].str.lower().str.endswith((".png", ".jpeg", ".jpg"))]

print(df.head(3))

df = df.rename(columns={"files": "image_uri"})
df["image_uri"] = df["image_uri"].apply(lambda x: os.path.join(images_path, x))

print(df["image_uri"])

db = lancedb.connect(VECDB_PATH)

if "dataset" in db:
    table = db["dataset"]
else:
    table = db.create_table("dataset", schema=Design)
table.add(df)
