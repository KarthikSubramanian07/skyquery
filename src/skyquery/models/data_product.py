"""Data products (FITS images, spectra) from archives."""

from __future__ import annotations

from pydantic import BaseModel, Field

from skyquery.models.provenance import Provenance
from skyquery.models.quantity import Measurement


class DataProduct(BaseModel):
    """A locatable archive product such as a FITS image or spectrum.

    Attributes:
        obs_id: The archive's observation identifier.
        title: A human-readable description.
        instrument: The instrument or collection, for example ``"JWST/NIRCam"``.
        product_type: For example ``"image"``, ``"spectrum"``, ``"timeseries"``.
        wavelength_band: The wavelength regime, for example ``"Infrared"``.
        access_url: A URL to retrieve or preview the product.
        exposure_time: Exposure time, when reported.
        position: The pointing, when reported (see :class:`SkyPosition`).
        provenance: Where the record came from and how to cite it.
    """

    obs_id: str
    title: str | None = None
    instrument: str | None = None
    product_type: str | None = None
    wavelength_band: str | None = None
    access_url: str | None = None
    exposure_time: Measurement | None = None
    provenance: Provenance


class DataProductList(BaseModel):
    """A set of data products matching a query."""

    query_target: str
    products: list[DataProduct] = Field(default_factory=list)
    total_found: int = 0
    provenance: Provenance
