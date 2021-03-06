import gzip
import os
from typing import Dict, List
from urllib.request import urlretrieve

import boto3
from botocore import UNSIGNED
from botocore.client import Config
import numpy as np
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly import colors
from plotly.subplots import make_subplots
import requests
from scipy import stats
from tqdm.notebook import tqdm


# =============================================================================
# Download Preprocessed Files from S3
# =============================================================================


def upload_s3_file(filename: str):
    """Uploads file to S3. Requires credentials with write permissions to exist
    as environment variables.
    """

    client = boto3.client("s3")
    client.upload_file(filename, "finm33150", filename)


def download_s3_file(filename: str):
    """Downloads file from read only S3 bucket."""

    client = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    client.download_file("finm33150", filename, filename)

# =============================================================================
# Charts
# =============================================================================

COLORS = colors.qualitative.T10

IS_labels = [
    ("obs", lambda x: f"{x:>7d}"),
    ("min:max", lambda x: f"{x[0]:>0.4f}:{x[1]:>0.3f}"),
    ("mean", lambda x: f"{x:>7.4f}"),
    ("std", lambda x: f"{x:>7.4f}"),
    ("skewness", lambda x: f"{x:>7.4f}"),
    ("kurtosis", lambda x: f"{x:>7.4f}"),
]


def get_moments_annotation(
    s: pd.Series,
    xref: str,
    yref: str,
    x: float,
    y: float,
    xanchor: str,
    title: str,
    labels: List,
) -> go.layout.Annotation:
    """Calculates summary statistics for a series and returns and
    Annotation object.
    """
    moments = list(stats.describe(s.to_numpy()))
    moments[3] = np.sqrt(moments[3])

    sharpe = s.mean() / s.std()

    return go.layout.Annotation(
        text=(
            f"<b>sharpe: {sharpe:>8.4f}</b><br>"
            + ("<br>").join(
                [f"{k[0]:<9}{k[1](moments[i])}" for i, k in enumerate(labels)]
            )
        ),
        align="left",
        showarrow=False,
        xref=xref,
        yref=yref,
        x=x,
        y=y,
        bordercolor="black",
        borderwidth=0.5,
        borderpad=2,
        bgcolor="white",
        xanchor=xanchor,
        yanchor="top",
    )


def make_components_chart(
    yc_L: str,
    fx_B: str,
    fx_L: str,
    libor: str,
    leverage: float,
    date_range: pd.date_range,
    dfs_yc: Dict,
    dfs_fx: Dict,
    dfs_libor: Dict,
) -> go.Figure:

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[
            f"5-Year Yield: {yc_L}",
            f"FX Rate: {fx_L}:{fx_B}",
            f"3 Month Libor: {libor}",
            f"FX Rate: {fx_B}:USD",
        ],
        vertical_spacing=0.09,
        horizontal_spacing=0.08,
        specs=[
            [{"secondary_y": True}, {"secondary_y": True}],
            [{"secondary_y": False}, {"secondary_y": True}],
        ],
    )

    # Lend market yield
    # =================
    fig.add_trace(
        go.Scatter(
            x=date_range,
            y=dfs_yc[yc_L].loc[date_range]["5-year"],
            line=dict(width=1, color=COLORS[0]),
            name=yc_L,
        ),
        row=1,
        col=1,
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=date_range,
            y=dfs_yc[yc_L].loc[date_range]["5-year"].pct_change() * 100,
            line=dict(width=1, color=COLORS[1], dash="dot"),
            name=yc_L,
        ),
        row=1,
        col=1,
        secondary_y=True,
    )

    # Borrow market fx
    # =================
    fig.add_trace(
        go.Scatter(
            x=date_range,
            y=dfs_fx[fx_B].loc[date_range].rate,
            line=dict(width=1, color=COLORS[0]),
            name=fx_B,
        ),
        row=2,
        col=2,
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=date_range,
            y=dfs_fx[fx_B].loc[date_range].rate.pct_change() * 100,
            line=dict(width=1, color=COLORS[1], dash="dot"),
            name=fx_B,
        ),
        row=2,
        col=2,
        secondary_y=True,
    )

    # Borrow market funding cost
    # =================
    fig.add_trace(
        go.Scatter(
            x=date_range,
            y=dfs_libor[libor].loc[date_range].value,
            line=dict(width=1, color=COLORS[0]),
            name=libor,
        ),
        row=2,
        col=1,
    )

    # Lend market fx cost
    # =================
    fx_BL = (
        dfs_fx[fx_L].loc[date_range].loc[date_range].rate
        / dfs_fx[fx_B].loc[date_range].rate
    )

    fig.add_trace(
        go.Scatter(
            x=date_range,
            y=fx_BL,
            line=dict(width=1, color=COLORS[0]),
            name=fx_L,
        ),
        row=1,
        col=2,
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=date_range,
            y=fx_BL.pct_change() * 100,
            line=dict(width=1, color=COLORS[1], dash="dot"),
            name=fx_L,
        ),
        row=1,
        col=2,
        secondary_y=True,
    )

    fig.update_xaxes(showline=True, linewidth=1, linecolor="grey", mirror=True)
    fig.update_yaxes(
        showline=True, linewidth=1, linecolor="grey", mirror=True, tickformat="0.1f"
    )

    fig.update_layout(
        title_text=(
            f"Weekly Carry Trade: Borrow {fx_B}, Lend {yc_L}"
            "<br>Underlying Securities: "
            f"{date_range.min().strftime('%Y-%m-%d')}"
            f" - {date_range.max().strftime('%Y-%m-%d')}"
        ),
        showlegend=False,
        height=600,
        font=dict(size=10),
        margin=dict(l=50, r=10, b=40, t=90),
        yaxis3=dict(tickformat="0.3f"),
    )

    for i in fig["layout"]["annotations"]:
        i["font"]["size"] = 12

    return fig


def make_returns_chart(df_ret: pd.DataFrame) -> go.Figure:

    fx_B, yc_L = df_ret.name.split(",")

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[
            f"Weekly Returns",
            f"Returns Distribution",
            f"Cumulative Returns",
            f"Q/Q Plot",
        ],
        vertical_spacing=0.09,
        horizontal_spacing=0.08,
    )

    # Returns Distribution
    returns = pd.cut(df_ret.per_return, 50).value_counts().sort_index()
    midpoints = returns.index.map(lambda interval: interval.right).to_numpy()
    norm_dist = stats.norm.pdf(
        midpoints, loc=df_ret.per_return.mean(), scale=df_ret.per_return.std()
    )

    fig.add_trace(
        go.Scatter(
            x=df_ret.index,
            y=df_ret.per_return * 100,
            line=dict(width=1, color=COLORS[0]),
            name="return",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_ret.index,
            y=df_ret.per_return.cumsum() * 100,
            line=dict(width=1, color=COLORS[0]),
            name="cum. return",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=[interval.mid for interval in returns.index],
            y=returns / returns.sum() * 100,
            name="pct. of returns",
            marker=dict(color=COLORS[0]),
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Scatter(
            x=[interval.mid for interval in returns.index],
            y=norm_dist / norm_dist.sum() * 100,
            name="normal",
            line=dict(width=1, color=COLORS[1]),
        ),
        row=1,
        col=2,
    )

    # Q/Q Data
    returns_norm = (
        (df_ret.per_return - df_ret.per_return.mean()) / df_ret.per_return.std()
    ).sort_values()
    norm_dist = pd.Series(
        list(map(stats.norm.ppf, np.linspace(0.001, 0.999, len(df_ret.per_return)))),
        name="normal",
    )

    fig.append_trace(
        go.Scatter(
            x=norm_dist,
            y=returns_norm,
            name="return norm.",
            mode="markers",
            marker=dict(color=COLORS[0], size=3),
        ),
        row=2,
        col=2,
    )

    fig.add_trace(
        go.Scatter(
            x=norm_dist,
            y=norm_dist,
            name="norm.",
            line=dict(width=1, color=COLORS[1]),
        ),
        row=2,
        col=2,
    )

    fig.add_annotation(
        text=(f"{df_ret.per_return.cumsum()[-1] * 100:0.2f}"),
        xref="paper",
        yref="y3",
        x=0.465,
        y=df_ret.per_return.cumsum()[-1] * 100,
        xanchor="left",
        showarrow=False,
        align="left",
    )

    fig.add_annotation(
        get_moments_annotation(
            df_ret.per_return,
            xref="paper",
            yref="paper",
            x=0.81,
            y=0.23,
            xanchor="left",
            title="Returns",
            labels=IS_labels,
        ),
        font=dict(size=6, family="Courier New, monospace"),
    )

    fig.update_xaxes(showline=True, linewidth=1, linecolor="black", mirror=True)
    fig.update_yaxes(showline=True, linewidth=1, linecolor="black", mirror=True)

    fig.update_layout(
        title_text=(
            f"Weekly Carry Trade: Borrow {fx_B}, Lend {yc_L}"
            "<br>Returns: "
            f"{df_ret.index.min().strftime('%Y-%m-%d')}"
            f" - {df_ret.index.max().strftime('%Y-%m-%d')}"
        ),
        showlegend=False,
        height=600,
        font=dict(size=10),
        margin=dict(l=50, r=50, b=50, t=100),
        yaxis=dict(tickformat="0.1f"),
        yaxis3=dict(tickformat="0.1f"),
        yaxis2=dict(tickformat="0.1f"),
        yaxis4=dict(tickformat="0.1f"),
        xaxis2=dict(tickformat="0.1f"),
        xaxis4=dict(tickformat="0.1f"),
    )

    for i in fig["layout"]["annotations"]:
        i["font"]["size"] = 12

    fig.update_annotations(font=dict(size=10))

    return fig
