from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.styles import COLORS


def apply_standard_layout(fig: go.Figure, height: int = 350) -> go.Figure:
    fig.update_layout(
        height=height,
        font_family="DM Sans",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0),
        title_font_size=14,
    )
    return fig


def funnel_chart(stages: list, values: list, title: str = "Funnel") -> go.Figure:
    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        marker_color=COLORS["chart_palette"][: len(stages)],
        textinfo="value+percent initial",
    ))
    fig.update_layout(title_text=title)
    return apply_standard_layout(fig)


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color_col: str | None = None,
    text_col: str | None = None,
    color: str = "#2D6A4F",
    orientation: str = "v",
) -> go.Figure:
    kwargs = dict(x=x, y=y, title=title, orientation=orientation)
    if color_col:
        kwargs["color"] = color_col
        kwargs["color_discrete_sequence"] = COLORS["chart_palette"]
    else:
        kwargs["color_discrete_sequence"] = [color]
    if text_col:
        kwargs["text"] = text_col
    fig = px.bar(df, **kwargs)
    if text_col:
        fig.update_traces(textposition="outside")
    return apply_standard_layout(fig)


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str = "#2D6A4F",
) -> go.Figure:
    fig = px.line(df, x=x, y=y, title=title, color_discrete_sequence=[color])
    fig.update_traces(line_width=2.5)
    return apply_standard_layout(fig)


def pie_chart(
    df: pd.DataFrame,
    values_col: str,
    names_col: str,
    title: str = "",
) -> go.Figure:
    fig = px.pie(
        df,
        values=values_col,
        names=names_col,
        title=title,
        color_discrete_sequence=COLORS["chart_palette"],
    )
    fig.update_traces(textinfo="label+percent", textposition="inside")
    return apply_standard_layout(fig)
