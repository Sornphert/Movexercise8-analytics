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
    barmode: str = "group",
    color_map: dict | None = None,
) -> go.Figure:
    kwargs = dict(x=x, y=y, title=title, orientation=orientation, barmode=barmode)
    if color_col:
        kwargs["color"] = color_col
        if color_map:
            kwargs["color_discrete_map"] = color_map
        else:
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


def heatmap_chart(
    df: pd.DataFrame,
    x_cols: list[str],
    y_col: str,
    title: str = "",
    color_scale: str = "Greens",
) -> go.Figure:
    z = df[x_cols].values
    fig = go.Figure(go.Heatmap(
        z=z,
        x=x_cols,
        y=df[y_col].tolist(),
        text=[[f"{v:.1f}%" for v in row] for row in z],
        texttemplate="%{text}",
        colorscale=color_scale,
        showscale=False,
    ))
    fig.update_layout(title_text=title, yaxis_autorange="reversed")
    return apply_standard_layout(fig, height=max(250, len(df) * 40 + 80))


def horizontal_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str = "#2D6A4F",
    text_col: str | None = None,
) -> go.Figure:
    fig = px.bar(
        df, x=x, y=y, title=title, orientation="h",
        color_discrete_sequence=[color],
        text=text_col,
    )
    if text_col:
        fig.update_traces(textposition="outside")
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return apply_standard_layout(fig, height=max(300, len(df) * 32 + 80))


def pie_chart(
    df: pd.DataFrame,
    values_col: str,
    names_col: str,
    title: str = "",
    color_map: dict | None = None,
) -> go.Figure:
    kwargs = dict(values=values_col, names=names_col, title=title)
    if color_map:
        kwargs["color"] = names_col
        kwargs["color_discrete_map"] = color_map
    else:
        kwargs["color_discrete_sequence"] = COLORS["chart_palette"]
    fig = px.pie(df, **kwargs)
    fig.update_traces(textinfo="label+percent", textposition="inside")
    return apply_standard_layout(fig)
