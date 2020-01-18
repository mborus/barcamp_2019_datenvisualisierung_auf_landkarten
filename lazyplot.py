try:
    from pandas.api.extensions import register_dataframe_accessor
except ImportError:
    # fuer Pandas 0.23.x auf Panda Flavors ausweichen
    from pandas_flavor import register_dataframe_accessor

import pandas as pd
from pathlib import Path
from tqdm import tqdm
import matplotlib.pyplot as plt
import geopandas as gpd
import geoplot as gplt
from shapely.geometry import Polygon, Point, box

BASE = Path("")
MAPDATA = (
    BASE / "ne_10m_admin_1_states_provinces" / "ne_10m_admin_1_states_provinces.shp"
)
GRIDFILE = BASE / r"Hexagone_125_km\Hexagone_125_km.shp"
PLZGEODATEN = BASE / r"geodaten_de.csv"

WORLD = gpd.read_file(str(MAPDATA))
GDF_GER = WORLD[WORLD["iso_a2"].isin(["DE"])]
GDF_GRID = gpd.read_file(str(GRIDFILE))
GDF_GER_BOX = gpd.GeoDataFrame(
    # [ 5.85248987 47.27112091 15.02205937 55.06533438]
    # add some border
    [box(5.3, 46.7, 15.5, 55.5)],
    columns=["geometry"],
    geometry="geometry",
    crs=GDF_GER.crs,
)
GDF_GER_INV = gpd.tools.overlay(GDF_GER, GDF_GER_BOX, how="symmetric_difference")
DF_PLZ = pd.read_csv(
    PLZGEODATEN,
    sep=";",
    dtype={0: "str", 1: "str", 2: "float", 3: "float"},
    encoding="latin-1",
).set_index("Plz")


@register_dataframe_accessor("lazyplot")
class LazyPlot:
    """Extra methods for lazyplot dataframes."""

    def __init__(self, df):
        self._df = df

    def date_plot(
        self,
        date_column=None,
        date_index=None,
        title=None,
        dayfirst=True,
        values=None,
        colors=None,
        show_legend=True,
        figsize=(15, 6),
    ):
        """print a date based plot of the data"""

        df_plot = self._df.copy()

        # TODO: Index based plot

        if date_column:
            if isinstance(date_column, str):
                df_plot.loc[:, date_column] = pd.to_datetime(
                    df_plot[date_column], dayfirst=dayfirst
                )
        df_plot = df_plot.set_index("datum")

        if isinstance(values, str):
            values = [values]

        if not isinstance(colors, list):
            colors = [f"C{i}" for i in range(len(values))]

        plt.figure(figsize=figsize)
        ax = plt.subplot(111)

        for i, value in enumerate(values):
            ax = df_plot[value].resample("D").sum().plot(color=colors[i], label=value)
        if show_legend:
            ax.legend()

        if title:
            plt.title(title)
        return plt.show()

    def group_by_plz(self):

        """Group data by German PLZ zip codes"""

        df_plz = DF_PLZ.copy()
        s_umsatz = (
            self._df.fillna(value={"plz": "XXXXX"})
            .groupby("plz")["betrag"]
            .sum()
            .fillna(0.0)
        )
        df_plz["betrag"] = s_umsatz
        return df_plz[~df_plz.betrag.isnull()]

    def plot_to_germany(self, figsize=(15, 6)):

        """plot grouped plz data on a map of Germany"""

        df_plot = self._df.copy()
        df_plot.columns = "ort", "lat", "lon", "sum"

        gdf_grid = GDF_GRID.copy()

        gdf_plot = gpd.GeoDataFrame(
            df_plot, geometry=[Point(x, y) for x, y in zip(df_plot.lon, df_plot.lat)]
        )
        spatial_index = gdf_plot.sindex
        sum_hex = []

        for index, row in tqdm(gdf_grid.iterrows()):
            polygon = row.geometry
            possible_matches_index = list(spatial_index.intersection(polygon.bounds))
            possible_matches = gdf_plot.iloc[possible_matches_index]
            precise_matches = possible_matches[possible_matches.within(polygon)]
            sum_hex.append(sum(precise_matches["sum"]))

        gdf_grid.loc[:, "sum"] = sum_hex
        gdf_grid_filtered = gdf_grid[gdf_grid["sum"] > 0.0]

        fig, ax = plt.subplots(figsize=(20, 20))
        fig.set_facecolor("grey")
        ax.set_aspect("equal")

        GDF_GER_BOX.plot(ax=ax, edgecolor="black", color="black", facecolor=None)
        gdf_grid_filtered.plot(
            ax=ax, column="sum", edgecolor="face", cmap="hot", linewidth=1, legend=True
        )
        GDF_GER.plot(ax=ax, color="none", edgecolor="white")
        GDF_GER_INV.plot(ax=ax, edgecolor="white", alpha=1.0)

        ax.set_ylim([49, 55.2])
        ax.set_xlim([8, 12])

        return plt.show()
