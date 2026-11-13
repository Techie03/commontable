"""Geometry column type that works on both PostgreSQL/PostGIS and SQLite.

On PostgreSQL the column is a real PostGIS geometry (GeoAlchemy2); on SQLite
it degrades to a plain TEXT column holding WKT. In both cases the Python-side
value is a WKT string (e.g. "POLYGON((...))" or "POINT(-97.13 33.21)"), so
application code never touches PostGIS functions and no test depends on them.

Serviceability in the slice uses the zone postal-code list as the primary
check; the geometry is stored for the production PostGIS path.
"""

from sqlalchemy import Text, types


class GeometryOrText(types.TypeDecorator):
    """WKT string on the Python side; Geometry on Postgres, TEXT on SQLite."""

    impl = Text
    cache_ok = True

    def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326):
        super().__init__()
        self.geometry_type = geometry_type
        self.srid = srid

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from geoalchemy2 import Geometry

            return Geometry(geometry_type=self.geometry_type, srid=self.srid)
        return Text()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            from geoalchemy2 import WKTElement

            if isinstance(value, str):
                return WKTElement(value, srid=self.srid)
            return value
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            # GeoAlchemy2 returns a WKBElement; convert back to WKT text.
            from shapely import wkb

            if hasattr(value, "data"):
                return wkb.loads(bytes(value.data)).wkt
            return str(value)
        return value
