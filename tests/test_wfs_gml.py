"""WFS 1.0.0 / GML2 -haku (lahteet.hae, tyyppi wfs_gml) ilman verkkoa."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from paikka import lahteet

GML = """<?xml version="1.0" encoding="utf-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs" xmlns:gml="http://www.opengis.net/gml"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:GIS="http://www.tekla.com/schemas/GIS"
 xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-basic.xsd">
 <gml:featureMember><GIS:Postinumeroalueet>
  <GIS:Postinumero>02130</GIS:Postinumero><GIS:Postinumero_fi>02130 ESPOO</GIS:Postinumero_fi>
  <GIS:Nimi>Tapiola – Hagalund ä ö å</GIS:Nimi>
  <GIS:Geometry><gml:Polygon srsName="{srs}"><gml:outerBoundaryIs><gml:LinearRing>
   <gml:coordinates>25490000,6672000 25490100,6672000 25490100,6672100
    25490000,6672100 25490000,6672000</gml:coordinates>
  </gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></GIS:Geometry>
 </GIS:Postinumeroalueet></gml:featureMember>
</wfs:FeatureCollection>"""

TYHJA = """<?xml version="1.0" encoding="utf-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs" xmlns:gml="http://www.opengis.net/gml">
</wfs:FeatureCollection>"""


class _Istunto:
    def __init__(self, sisalto: str) -> None:
        self.sisalto = sisalto.encode("utf-8")
        self.parametrit: dict[str, Any] = {}

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: float = 0) -> requests.Response:
        self.parametrit = params or {}
        r = requests.Response()
        r.status_code = 200
        r._content = self.sisalto
        return r


def _lahde(epsg: int = 3879) -> lahteet.Lahde:
    return lahteet.Lahde(
        id="gml_testi",
        nimi="testi",
        tyyppi="wfs_gml",
        url="https://example.invalid/wfs.ashx",
        epsg=epsg,
        lisenssi="CC BY 4.0",
        attribuutio="testi",
        kokoelma="GIS:Postinumeroalueet",
    )


@pytest.mark.parametrize(
    "srs",
    ["http://www.opengis.net/gml/srs/epsg.xml#3879", "EPSG:3879", "urn:ogc:def:crs:EPSG::3879"],
)
def test_gml_luetaan_ilman_verkkoa(srs: str) -> None:
    istunto = _Istunto(GML.format(srs=srs))
    gdf = lahteet.hae(_lahde(), istunto=istunto)
    assert len(gdf) == 1
    assert gdf.crs.to_epsg() == 3879
    assert gdf.geometry.iloc[0].bounds == (25490000, 6672000, 25490100, 6672100)  # x=itä, y=pohjoinen
    assert gdf["Postinumero"].iloc[0] == "02130"  # etunolla säilyy
    assert gdf["Nimi"].iloc[0] == "Tapiola – Hagalund ä ö å"
    assert istunto.parametrit["version"] == "1.0.0"
    assert istunto.parametrit["srsName"] == "EPSG:3879"


def test_eri_jarjestelma_keskeyttaa() -> None:
    with pytest.raises(ValueError, match="3067"):
        lahteet.hae(_lahde(), istunto=_Istunto(GML.format(srs="EPSG:3067")))


def test_palvelun_virhe() -> None:
    virhe = '<?xml version="1.0"?><ServiceExceptionReport><ServiceException>Unknown type</ServiceException>'
    with pytest.raises(RuntimeError, match="Unknown type"):
        lahteet.hae(_lahde(), istunto=_Istunto(virhe + "</ServiceExceptionReport>"))


def test_tyhja_vastaus() -> None:
    gdf = lahteet.hae(_lahde(), istunto=_Istunto(TYHJA))
    assert gdf.empty and gdf.crs.to_epsg() == 3879


def test_rajaus_vain_lahteen_jarjestelmassa() -> None:
    istunto = _Istunto(GML.format(srs="EPSG:3879"))
    lahteet.hae(_lahde(), rajaus=(1, 2, 3, 4), istunto=istunto)
    assert istunto.parametrit["bbox"] == "1,2,3,4"
    with pytest.raises(ValueError, match="EPSG:3879"):
        lahteet.hae(_lahde(), rajaus=(24.5, 60.1, 24.9, 60.3), rajaus_epsg=4326, istunto=istunto)
