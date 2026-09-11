#!/usr/bin/env python3
"""Build Shortcuts for PHA HealthKit ingest + the daily fact card.

Two outputs, never mixed:

* **Public template** (``shortcuts/pha-daily.*``) — no token, no machine host.
  Import Questions ask for Mac URL + token. Left **unsigned** so an Apple ID
  is not embedded in git. Clone users enable Allow Untrusted Shortcuts.
* **Local signed copies** (``data/local_shortcuts/``, gitignored) — bake this
  Mac's URL + ``PHA_INGEST_TOKEN``. Never copy that folder into git.

``--public`` refuses to write if a leak scan finds this machine's token,
hostname, or LAN IP in the workflow.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Union
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "data" / "local_shortcuts"
PUBLIC_DIR = ROOT / "shortcuts"
OBJ = "\ufffc"
PUBLIC_NAME = "PHA Daily"
PUBLIC_BASE_PLACEHOLDER = "http://Mac.local:8788"
PUBLIC_TOKEN_PLACEHOLDER = ""
BASE_VAR = "PHA Base"
TOKEN_VAR = "PHA Token"
_PHA_DAILY_NS = uuid.UUID("e7c0f0a0-5c11-4d2a-9b3e-0f1a2b3c4d5e")
UrlSpec = Union[str, list, dict]
TokenSpec = Union[str, tuple[str, str]]
_stable_uuids: Optional[list[int]] = None


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.is_file():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'").strip('"')
    return env


@contextmanager
def stable_uuids() -> Iterator[None]:
    """Deterministic UUIDs so the public template is reviewable in git."""
    global _stable_uuids
    prev = _stable_uuids
    _stable_uuids = [0]
    try:
        yield
    finally:
        _stable_uuids = prev


def _uuid() -> str:
    if _stable_uuids is not None:
        _stable_uuids[0] += 1
        return str(uuid.uuid5(_PHA_DAILY_NS, f"pha-daily-{_stable_uuids[0]}")).upper()
    return str(uuid.uuid4()).upper()


def _icon() -> dict:
    return {"WFWorkflowIconGlyphNumber": 59836, "WFWorkflowIconStartColor": 431817727}


def _token_item(key: str, output_uuid: str, output_name: str) -> dict:
    return {
        "WFItemType": 0,
        "WFKey": {
            "Value": {"string": key},
            "WFSerializationType": "WFTextTokenString",
        },
        "WFValue": _text_with_refs([(output_uuid, output_name)]),
    }


def _header_item(key: str, value: str) -> dict:
    return {
        "WFItemType": 0,
        "WFKey": {
            "Value": {"string": key},
            "WFSerializationType": "WFTextTokenString",
        },
        "WFValue": {
            "Value": {"string": value},
            "WFSerializationType": "WFTextTokenString",
        },
    }


def _headers(token: str) -> dict:
    return {
        "Value": {
            "WFDictionaryFieldValueItems": [
                _header_item("Content-Type", "application/json"),
                _header_item("X-PHA-Ingest-Token", token),
            ]
        },
        "WFSerializationType": "WFDictionaryFieldValue",
    }


def _headers_from_ref(token_uuid: str, token_name: str) -> dict:
    return {
        "Value": {
            "WFDictionaryFieldValueItems": [
                _header_item("Content-Type", "application/json"),
                _token_item("X-PHA-Ingest-Token", token_uuid, token_name),
            ]
        },
        "WFSerializationType": "WFDictionaryFieldValue",
    }


def _coerce_url(url: UrlSpec) -> str | dict:
    if isinstance(url, str):
        return url
    if isinstance(url, dict):
        return url
    return _text_with_refs(list(url))


def _coerce_headers(token: TokenSpec) -> dict:
    if isinstance(token, tuple):
        return _headers_from_ref(token[0], token[1])
    return _headers(token)


def _output_ref(output_uuid: str, name: str) -> dict:
    return {
        "Value": {
            "OutputName": name,
            "OutputUUID": output_uuid,
            "Type": "ActionOutput",
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def _variable_input(output_uuid: str, name: str) -> dict:
    """If/Repeat WFInput must wrap the attachment; bare tokens import as a blank Condition."""
    return {
        "Type": "Variable",
        "Variable": _output_ref(output_uuid, name),
    }


def _text_with_refs(template_parts: list[str | tuple[str, str]]) -> dict:
    """Build WFTextTokenString. tuple is (output_uuid, output_name)."""
    s = ""
    attachments: dict = {}
    for part in template_parts:
        if isinstance(part, tuple):
            start = len(s)
            s += OBJ
            attachments[f"{{{start}, 1}}"] = {
                "OutputName": part[1],
                "OutputUUID": part[0],
                "Type": "ActionOutput",
            }
        else:
            s += part
    value: dict = {"string": s}
    if attachments:
        value["attachmentsByRange"] = attachments
    return {"Value": value, "WFSerializationType": "WFTextTokenString"}


def _action(identifier: str, params: dict) -> dict:
    return {
        "WFWorkflowActionIdentifier": identifier,
        "WFWorkflowActionParameters": params,
    }


def _workflow(
    name: str,
    actions: list[dict],
    *,
    import_questions: Optional[list] = None,
) -> dict:
    return {
        "WFWorkflowActions": actions,
        "WFWorkflowClientVersion": "2700.0.4",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowIcon": _icon(),
        "WFWorkflowImportQuestions": list(import_questions or []),
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowName": name,
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": [],
    }


def _downloadurl(
    url: UrlSpec,
    token: TokenSpec,
    body_uuid: str,
    body_name: str,
    action_uuid: str,
) -> dict:
    return _action(
        "is.workflow.actions.downloadurl",
        {
            "UUID": action_uuid,
            "WFURL": _coerce_url(url),
            "WFHTTPMethod": "POST",
            "WFHTTPBodyType": "File",
            "WFHTTPHeaders": _coerce_headers(token),
            "WFRequestVariable": _output_ref(body_uuid, body_name),
        },
    )


def _geturl(url: UrlSpec, token: TokenSpec, action_uuid: str, out_name: str) -> dict:
    return _action(
        "is.workflow.actions.downloadurl",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFURL": _coerce_url(url),
            "WFHTTPMethod": "GET",
            "WFHTTPHeaders": _coerce_headers(token),
        },
    )


def _make_url(url: UrlSpec, action_uuid: str, name: str) -> dict:
    """Create a URL item. Open URLs cannot take a raw WFURL string (shows「无 URL」)."""
    return _action(
        "is.workflow.actions.url",
        {
            "UUID": action_uuid,
            "CustomOutputName": name,
            "WFURLActionURL": _coerce_url(url),
        },
    )


def _dict_value(src_uuid: str, src_name: str, key: str, action_uuid: str, out_name: str) -> dict:
    return _action(
        "is.workflow.actions.getvalueforkey",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFDictionaryKey": key,
            "WFInput": _output_ref(src_uuid, src_name),
        },
    )


def _openurl(src_uuid: str, src_name: str) -> dict:
    return _action(
        "is.workflow.actions.openurl",
        {"WFInput": _output_ref(src_uuid, src_name)},
    )


def build_fact_card(url: UrlSpec, view_url: UrlSpec, token: TokenSpec) -> dict:
    """GET teaser JSON → short lock-screen note → open full HTML card."""
    get_id = _uuid()
    note_id = _uuid()
    title_id = _uuid()
    body_id = _uuid()
    card_url_id = _uuid()
    actions = [
        _geturl(url, token, get_id, "Fact Card"),
        _dict_value(get_id, "Fact Card", "notification", note_id, "Notification"),
        _dict_value(note_id, "Notification", "title", title_id, "Title"),
        _dict_value(note_id, "Notification", "body", body_id, "Body"),
        _make_url(view_url, card_url_id, "Card URL"),
        _action(
            "is.workflow.actions.notification",
            {
                "UUID": _uuid(),
                "WFNotificationActionTitle": _text_with_refs([(title_id, "Title")]),
                "WFNotificationActionBody": _text_with_refs([(body_id, "Body")]),
            },
        ),
        _openurl(card_url_id, "Card URL"),
    ]
    return _workflow("PHA 事实卡通知", actions)


def build_probe(url: str, token: str) -> dict:
    now = datetime.now(ZoneInfo("Asia/Shanghai")).replace(microsecond=0).isoformat()
    body = (
        '{"user_id":"shortcut_probe","samples":['
        '{"metric_type":"steps","timestamp":"' + now + '","value":1,'
        '"unit":"count","source":"healthkit"}]}'
    )
    text_id = _uuid()
    url_id = _uuid()
    actions = [
        _action(
            "is.workflow.actions.gettext",
            {"UUID": text_id, "CustomOutputName": "JSON", "WFTextActionText": body},
        ),
        _downloadurl(url, token, text_id, "JSON", url_id),
        _action(
            "is.workflow.actions.showresult",
            {
                "Text": _text_with_refs(
                    ["PHA ingest 探测结果：", (url_id, "Contents of URL")]
                )
            },
        ),
    ]
    return _workflow("PHA ingest 探测", actions)


def _find_health(
    sample_type: str,
    action_uuid: str,
    out_name: str = "Health Samples",
    *,
    unit: str = "",
    last_days: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict:
    """Health quantity Find. Default = today. ``last_days`` uses the sleep D1 predicate."""
    date_pred: dict
    if last_days is not None:
        date_pred = {
            "Bounded": True,
            "Operator": 1001,
            "Property": "Start Date",
            "Removable": False,
            "Values": {"Number": int(last_days), "Unit": 16384},
        }
    else:
        date_pred = {
            "Bounded": True,
            "Operator": 1002,
            "Property": "Start Date",
            "Removable": False,
            "Values": {"Number": "7", "Unit": 16},
        }
    params: dict = {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFContentItemLimitEnabled": False,
            "WFContentItemFilter": {
                "Value": {
                    "WFActionParameterFilterPrefix": 1,
                    "WFContentPredicateBoundedDate": False,
                    "WFActionParameterFilterTemplates": [
                        {
                            "Bounded": True,
                            "Operator": 4,
                            "Property": "Type",
                            "Removable": False,
                            "Values": {
                                "Enumeration": {
                                    "Value": sample_type,
                                    "WFSerializationType": "WFStringSubstitutableState",
                                }
                            },
                        },
                        date_pred,
                    ],
                },
                "WFSerializationType": "WFContentPredicateTableTemplate",
            },
    }
    if limit is not None:
        params["WFContentItemLimitEnabled"] = True
        params["WFContentItemLimitNumber"] = int(limit)
        params["WFContentItemSortProperty"] = "Start Date"
        params["WFContentItemSortOrder"] = "Latest First"
    # Find picker label must come from shortcut_health_find_catalog.json
    # (device_verified only). Never guess SDK / Health-app titles.
    if unit == "count/min":
        params["WFHealthActionUnit"] = unit
    return _action("is.workflow.actions.filter.health.quantity", params)


def _item_from_list(
    src_uuid: str,
    src_name: str,
    action_uuid: str,
    out_name: str,
    *,
    specifier: str = "First Item",
) -> dict:
    return _action(
        "is.workflow.actions.getitemfromlist",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFItemSpecifier": specifier,
            "WFInput": _output_ref(src_uuid, src_name),
        },
    )


def _if_has_any(src_uuid: str, src_name: str, grouping: str) -> dict:
    """Skip the block when Find returned no Health samples (Condition = has any value)."""
    return _action(
        "is.workflow.actions.conditional",
        {
            "GroupingIdentifier": grouping,
            "WFControlFlowMode": 0,
            "WFCondition": 100,
            "WFInput": _variable_input(src_uuid, src_name),
        },
    )


def _endif(grouping: str) -> dict:
    return _action(
        "is.workflow.actions.conditional",
        {
            "GroupingIdentifier": grouping,
            "WFControlFlowMode": 2,
        },
    )


def _get_detail(src_uuid: str, src_name: str, prop: str, action_uuid: str, out_name: str) -> dict:
    return _action(
        "is.workflow.actions.properties.health.quantity",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFContentItemPropertyName": prop,
            "WFInput": _output_ref(src_uuid, src_name),
        },
    )


def _detect_number(src_uuid: str, src_name: str, action_uuid: str, out_name: str) -> dict:
    return _action(
        "is.workflow.actions.detect.number",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFInput": _output_ref(src_uuid, src_name),
        },
    )


def _statistics(
    src_uuid: str,
    src_name: str,
    operation: str,
    action_uuid: str,
    out_name: str,
) -> dict:
    ref = _output_ref(src_uuid, src_name)
    return _action(
        "is.workflow.actions.statistics",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFStatisticsOperation": operation,
            "Input": ref,
            "WFInput": ref,
        },
    )


def _sync_one_metric(
    url: UrlSpec, token: TokenSpec, spec, *, pack_version: str = ""
) -> tuple[list[dict], str, str, str, str]:
    """Find → if empty skip POST. Accrual = today Sum; lagged/latest = last N + date; overnight = last N Average.

    Unit is the registry literal. Get Details Unit on a Find list concatenates
    every sample (``count\\ncount\\n…``) and iOS dies on large overnight lists.
    """
    find_id = _uuid()
    group = _uuid()
    val_id = _uuid()
    num_id = _uuid()
    stat_id = _uuid()
    plain_id = _uuid()
    start_id = _uuid()
    first_id = _uuid()
    text_id = _uuid()
    json_id = _uuid()
    resp_id = _uuid()
    samples_name = f"{spec.metric_id} Samples"
    value_name = f"{spec.metric_id} Value"
    numbers_name = f"{spec.metric_id} Numbers"
    stat_name = f"{spec.metric_id} Stat"
    plain_name = f"{spec.metric_id} Number"
    start_name = f"{spec.metric_id} Start"
    first_name = f"{spec.metric_id} First"
    text_name = f"{spec.metric_id} Text"
    json_name = f"{spec.metric_id} JSON"
    resp_name = f"{spec.metric_id} Response"
    post = _downloadurl(url, token, json_id, json_name, resp_id)
    post["WFWorkflowActionParameters"]["CustomOutputName"] = resp_name
    unit = spec.unit_health or spec.unit or "count"
    kind = getattr(spec, "temporal_kind", "") or ""
    dated = kind in {"daily_lagged", "latest", "overnight"}
    last_days = int(getattr(spec, "freshness_days", 2) or 2) if dated else None
    single = kind in {"daily_lagged", "latest"}
    find_limit = 1 if single else (150 if kind == "overnight" else None)
    pack = pack_version or ""
    find = _find_health(
        spec.health_type,
        find_id,
        samples_name,
        unit=unit,
        last_days=last_days,
        limit=find_limit,
    )
    json_unit_parts: list[str | tuple[str, str]] = [
        '{"user_id":"default","pack_version":"',
        pack,
        '","samples":[{"metric_type":"',
        spec.ingest_key,
        '","timestamp":"',
    ]
    if dated:
        inner: list[dict] = []
        if single:
            inner.append(_get_detail(find_id, samples_name, "Start Date", start_id, start_name))
        else:
            inner.append(_item_from_list(find_id, samples_name, first_id, first_name))
            inner.append(_get_detail(first_id, first_name, "Start Date", start_id, start_name))
        inner.extend(
            [
                _get_detail(find_id, samples_name, "Value", val_id, value_name),
                _detect_number(val_id, value_name, num_id, numbers_name),
            ]
        )
        if single:
            inner.append(_detect_number(val_id, value_name, plain_id, plain_name))
            stat_id, stat_name = plain_id, plain_name
        else:
            inner.append(_statistics(num_id, numbers_name, spec.stat, stat_id, stat_name))
            inner.append(_detect_number(stat_id, stat_name, plain_id, plain_name))
        json_unit_parts.extend(
            [
                (start_id, start_name),
                '","value":"',
                (text_id, text_name),
                '","unit":"',
                unit,
                '","source":"healthkit"}]}',
            ]
        )
        inner.extend(
            [
            _action(
                "is.workflow.actions.gettext",
                {
                    "UUID": text_id,
                    "CustomOutputName": text_name,
                    "WFTextActionText": _text_with_refs([(plain_id, plain_name)]),
                },
            ),
            _action(
                "is.workflow.actions.gettext",
                {
                    "UUID": json_id,
                    "CustomOutputName": json_name,
                    "WFTextActionText": _text_with_refs(json_unit_parts),
                },
            ),
            post,
            ]
        )
    else:
        inner = [
            _get_detail(find_id, samples_name, "Value", val_id, value_name),
            _detect_number(val_id, value_name, num_id, numbers_name),
            _statistics(num_id, numbers_name, spec.stat, stat_id, stat_name),
            _detect_number(stat_id, stat_name, plain_id, plain_name),
            _action(
                "is.workflow.actions.gettext",
                {
                    "UUID": text_id,
                    "CustomOutputName": text_name,
                    "WFTextActionText": _text_with_refs([(plain_id, plain_name)]),
                },
            ),
            _action(
                "is.workflow.actions.gettext",
                {
                    "UUID": json_id,
                    "CustomOutputName": json_name,
                    "WFTextActionText": _text_with_refs(
                        [
                            '{"user_id":"default","pack_version":"',
                            pack,
                            '","samples":[{"metric_type":"',
                            spec.ingest_key,
                            '","timestamp":"","value":"',
                            (text_id, text_name),
                            '","unit":"',
                            unit,
                            '","source":"healthkit"}]}',
                        ]
                    ),
                },
            ),
            post,
        ]
    actions = [
        find,
        _if_has_any(find_id, samples_name, group),
        *inner,
        _endif(group),
    ]
    return actions, stat_id, stat_name, resp_id, resp_name


def _find_sleep(
    action_uuid: str,
    out_name: str,
    *,
    variant: str = "d1",
    limit: int = 150,
) -> dict:
    """Sleep Find. D1 = last 2 days, newest 150. is_today = the already-working filter.

    Device evidence 2026-09-07 15:02: Type Sleep + sort/limit and *no* date
    predicate POSTs empty VALUES (Health Find returns []). last 1 day without
    Limit previously crashed Get Details; Limit 150 stays on to cap the list.
    """
    templates: list[dict] = [
        {
            "Bounded": True,
            "Operator": 4,
            "Property": "Type",
            "Removable": False,
            "Values": {
                "Enumeration": {
                    "Value": "Sleep",
                    "WFSerializationType": "WFStringSubstitutableState",
                }
            },
        },
    ]
    params: dict = {
        "UUID": action_uuid,
        "CustomOutputName": out_name,
        "WFContentItemLimitEnabled": False,
        "WFContentItemFilter": {
            "Value": {
                "WFActionParameterFilterPrefix": 1,
                "WFContentPredicateBoundedDate": False,
                "WFActionParameterFilterTemplates": templates,
            },
            "WFSerializationType": "WFContentPredicateTableTemplate",
        },
    }
    if variant == "is_today":
        templates.append(
            {
                "Bounded": True,
                "Operator": 1002,
                "Property": "Start Date",
                "Removable": False,
                "Values": {"Number": "7", "Unit": 16},
            }
        )
    else:
        templates.append(
            {
                "Bounded": True,
                "Operator": 1001,
                "Property": "Start Date",
                "Removable": False,
                "Values": {"Number": 2, "Unit": 16384},
            }
        )
        params["WFContentItemLimitEnabled"] = True
        params["WFContentItemLimitNumber"] = int(limit)
        params["WFContentItemSortProperty"] = "Start Date"
        params["WFContentItemSortOrder"] = "Latest First"
    return _action("is.workflow.actions.filter.health.quantity", params)


def _find_all_sleep(action_uuid: str, out_name: str) -> dict:
    """Type Sleep + last 1 day. No Value row — incomplete enum crashes the run."""
    params = {
        "UUID": action_uuid,
        "CustomOutputName": out_name,
        "WFContentItemLimitEnabled": False,
        "WFContentItemFilter": {
            "Value": {
                "WFActionParameterFilterPrefix": 1,
                "WFContentPredicateBoundedDate": False,
                "WFActionParameterFilterTemplates": [
                    {
                        "Bounded": True,
                        "Operator": 4,
                        "Property": "Type",
                        "Removable": False,
                        "Values": {
                            "Enumeration": {
                                "Value": "Sleep",
                                "WFSerializationType": "WFStringSubstitutableState",
                            }
                        },
                    },
                    {
                        "Bounded": True,
                        "Operator": 1001,
                        "Property": "Start Date",
                        "Removable": False,
                        "Values": {"Number": 1, "Unit": 16384},
                    },
                ],
            },
            "WFSerializationType": "WFContentPredicateTableTemplate",
        },
    }
    return _action("is.workflow.actions.filter.health.quantity", params)


def build_sleep(
    url: UrlSpec,
    token: TokenSpec,
    specs: list,
    *,
    variant: str = "d1",
    limit: int = 150,
    show_result: bool = True,
    skip_if_empty: bool = False,
) -> dict:
    """Find Sleep → Value/Start/End (+ Source/Device) text → File POST → show JSON."""
    name = "PHA 同步睡眠" if variant != "is_today" else "PHA 同步睡眠（is today 备选）"
    if not specs:
        return _workflow(
            name,
            [
                _action(
                    "is.workflow.actions.showresult",
                    {
                        "Text": _text_with_refs(
                            [
                                "注册表里没有可同步的睡眠分期。",
                            ]
                        )
                    },
                )
            ],
        )
    find_id = _uuid()
    value_id = _uuid()
    start_id = _uuid()
    end_id = _uuid()
    source_id = _uuid()
    device_id = _uuid()
    text_id = _uuid()
    resp_id = _uuid()
    post = _downloadurl(url, token, text_id, "Sleep Bundle", resp_id)
    post["WFWorkflowActionParameters"]["CustomOutputName"] = "Sleep Response"
    find_action = _find_sleep(find_id, "Sleep Samples", variant=variant, limit=limit)
    inner: list[dict] = [
        _get_detail(find_id, "Sleep Samples", "Value", value_id, "Sleep Values"),
        _get_detail(find_id, "Sleep Samples", "Start Date", start_id, "Sleep Starts"),
        _get_detail(find_id, "Sleep Samples", "End Date", end_id, "Sleep Ends"),
        _get_detail(find_id, "Sleep Samples", "Source", source_id, "Sleep Sources"),
        _get_detail(find_id, "Sleep Samples", "Device", device_id, "Sleep Devices"),
        _action(
            "is.workflow.actions.gettext",
            {
                "UUID": text_id,
                "CustomOutputName": "Sleep Bundle",
                "WFTextActionText": _text_with_refs(
                    [
                        "PHA_SLEEP_V1\nuser_id=default\n---VALUES---\n",
                        (value_id, "Sleep Values"),
                        "\n---STARTS---\n",
                        (start_id, "Sleep Starts"),
                        "\n---ENDS---\n",
                        (end_id, "Sleep Ends"),
                        "\n---SOURCES---\n",
                        (source_id, "Sleep Sources"),
                        "\n---DEVICES---\n",
                        (device_id, "Sleep Devices"),
                    ]
                ),
            },
        ),
        post,
    ]
    if show_result:
        inner.append(
            _action(
                "is.workflow.actions.showresult",
                {
                    "Text": _text_with_refs(
                        [
                            "PHA睡眠上传\n",
                            (text_id, "Sleep Bundle"),
                            "\n服务器：",
                            (resp_id, "Sleep Response"),
                        ]
                    )
                },
            )
        )
    if skip_if_empty:
        group = _uuid()
        actions = [
            find_action,
            _if_has_any(find_id, "Sleep Samples", group),
            *inner,
            _endif(group),
        ]
    else:
        actions = [find_action, *inner]
    return _workflow(name, actions)


def build_health(
    url: UrlSpec,
    token: TokenSpec,
    specs: list,
    *,
    pack_version: str = "",
    show_result: bool = True,
) -> dict:
    """iPhone-only: one POST per registry quantity type (do not POST Health items)."""
    if not specs:
        return _workflow(
            "PHA 同步健康",
            [
                _action(
                    "is.workflow.actions.showresult",
                    {
                        "Text": _text_with_refs(
                            [
                                "注册表里没有可按日合计的 Health 数量类型。",
                            ]
                        )
                    },
                )
            ],
        )
    actions: list[dict] = []
    result_parts: list[str | tuple[str, str]] = []
    for spec in specs:
        block, stat_id, stat_name, resp_id, resp_name = _sync_one_metric(
            url, token, spec, pack_version=pack_version
        )
        actions.extend(block)
        if result_parts:
            result_parts.append("\n")
        result_parts.extend(
            [
                spec.label,
                " ",
                spec.stat,
                "：",
                (stat_id, stat_name),
                "\n服务器：",
                (resp_id, resp_name),
            ]
        )
    if show_result:
        actions.append(
            _action(
                "is.workflow.actions.showresult",
                {"Text": _text_with_refs(result_parts)},
            )
        )
    return _workflow("PHA 同步健康", actions)


def _import_questions() -> list[dict]:
    return [
        {
            "ActionIndex": 0,
            "Category": "Parameter",
            "ParameterKey": "WFTextActionText",
            "Text": "PHA Mac URL on this Wi-Fi (not localhost). Example: http://Mac.local:8788",
            "DefaultValue": PUBLIC_BASE_PLACEHOLDER,
        },
        {
            "ActionIndex": 1,
            "Category": "Parameter",
            "ParameterKey": "WFTextActionText",
            "Text": "PHA_INGEST_TOKEN from your Mac .env — private, never from GitHub",
            "DefaultValue": "",
        },
    ]


def build_daily(
    *,
    base_text: str,
    token_text: str,
    specs: list,
    sleep_specs: list,
    pack_version: str,
    import_questions: bool,
) -> dict:
    """One run: sleep + quantity pack + lock-screen teaser + open the full card.

    No Show Result (would block morning automation). Sleep Find empty → skip POST.
    """
    base_id = _uuid()
    token_id = _uuid()
    actions: list[dict] = [
        _action(
            "is.workflow.actions.gettext",
            {
                "UUID": base_id,
                "CustomOutputName": BASE_VAR,
                "WFTextActionText": base_text,
            },
        ),
        _action(
            "is.workflow.actions.gettext",
            {
                "UUID": token_id,
                "CustomOutputName": TOKEN_VAR,
                "WFTextActionText": token_text,
            },
        ),
    ]
    ingest: list = [(base_id, BASE_VAR), "/ingest/healthkit"]
    fact_get: list = [(base_id, BASE_VAR), "/proactive/fact-card?user_id=default"]
    fact_view: list = [
        (base_id, BASE_VAR),
        "/proactive/fact-card/view?user_id=default&token=",
        (token_id, TOKEN_VAR),
    ]
    token_ref = (token_id, TOKEN_VAR)
    if sleep_specs:
        sleep_wf = build_sleep(
            ingest,
            token_ref,
            sleep_specs,
            variant="d1",
            show_result=False,
            skip_if_empty=True,
        )
        actions.extend(sleep_wf["WFWorkflowActions"])
    if specs:
        health_wf = build_health(
            ingest,
            token_ref,
            specs,
            pack_version=pack_version,
            show_result=False,
        )
        actions.extend(health_wf["WFWorkflowActions"])
    actions.extend(
        build_fact_card(fact_get, fact_view, token_ref)["WFWorkflowActions"]
    )
    questions = _import_questions() if import_questions else []
    return _workflow(PUBLIC_NAME, actions, import_questions=questions)


def build_daily_public() -> dict:
    from pha.healthkit_sync_plan import shortcut_sleep_specs, shortcut_sync_specs
    from pha.wearable_metric_registry import shortcut_pack_version

    with stable_uuids():
        return build_daily(
            base_text=PUBLIC_BASE_PLACEHOLDER,
            token_text=PUBLIC_TOKEN_PLACEHOLDER,
            specs=shortcut_sync_specs("default"),
            sleep_specs=shortcut_sleep_specs("default"),
            pack_version=shortcut_pack_version(),
            import_questions=True,
        )


def _machine_needles(env: dict[str, str]) -> list[str]:
    """Values that must never appear in the GitHub template."""
    needles: list[str] = []

    def add(raw: object) -> None:
        v = str(raw or "").strip().strip("'").strip('"')
        if len(v) < 8:
            return
        if v == PUBLIC_BASE_PLACEHOLDER or v == PUBLIC_TOKEN_PLACEHOLDER:
            return
        if v in PUBLIC_BASE_PLACEHOLDER:
            return
        if v not in needles:
            needles.append(v)

    for key in ("PHA_INGEST_TOKEN", "PHA_INGEST_URL_HOST"):
        add(env.get(key, ""))
        add(os.environ.get(key, ""))
    try:
        name = subprocess.check_output(
            ["scutil", "--get", "LocalHostName"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        name = ""
    if name:
        add(name)
        add(f"{name}.local")
    try:
        computer = subprocess.check_output(
            ["scutil", "--get", "ComputerName"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        computer = ""
    add(computer)
    for iface in ("en0", "en1", "en2"):
        try:
            ip = subprocess.check_output(
                ["ipconfig", "getifaddr", iface], text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            ip = ""
        add(ip)
    return needles


def public_template_leak(blob: str | bytes, env: Optional[dict[str, str]] = None) -> str:
    text = blob.decode("latin-1") if isinstance(blob, bytes) else blob
    for needle in _machine_needles(env or _load_env()):
        if needle in text:
            return "machine secret or hostname would ship in the public shortcut"
    lowered = text.lower()
    for banned in ("wenhuidemacbook",):
        if banned in lowered:
            return "banned personal hostname fragment in public shortcut"
    return ""


def _sign(src: Path, dest: Path, *, mode: str = "anyone") -> None:
    subprocess.run(
        [
            "shortcuts",
            "sign",
            "--mode",
            mode,
            "--input",
            str(src),
            "--output",
            str(dest),
        ],
        check=True,
    )


def _write_signed(dir_path: Path, stem: str, wf: dict, *, mode: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    xml_path = dir_path / f"{stem}.plist"
    unsigned_path = dir_path / f"{stem}.unsigned.shortcut"
    signed_path = dir_path / f"{stem}.shortcut"
    xml_path.write_bytes(plistlib.dumps(wf, fmt=plistlib.FMT_XML))
    unsigned_path.write_bytes(plistlib.dumps(wf, fmt=plistlib.FMT_BINARY))
    dest = Path("/tmp") / f"{stem}.shortcut"
    if dest.exists():
        dest.unlink()
    if signed_path.exists():
        signed_path.unlink()
    _sign(unsigned_path, dest, mode=mode)
    signed_path.write_bytes(dest.read_bytes())
    print(f"OK {signed_path} mode={mode}")
    return signed_path


def _validate_sync_plan(sync_specs: list) -> Optional[str]:
    from pha.shortcut_find_catalog import never_use_find_labels

    banned = set(never_use_find_labels())
    bad = [s.health_type for s in sync_specs if s.health_type in banned]
    if bad:
        return f"forbidden Find labels in sync plan: {bad}"
    if any(s.metric_id == "wrist_temp" for s in sync_specs):
        return "wrist_temp is not device_verified; do not emit Find"
    return None


def emit_public() -> int:
    """Write the GitHub template. Unsigned on purpose — signing embeds an Apple ID."""
    env = _load_env()
    wf = build_daily_public()
    reason = public_template_leak(str(wf), env)
    if reason:
        print(f"FAIL {reason}", file=sys.stderr)
        return 1
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    plist_path = PUBLIC_DIR / "pha-daily.plist"
    shortcut_path = PUBLIC_DIR / "pha-daily.shortcut"
    xml = plistlib.dumps(wf, fmt=plistlib.FMT_XML)
    binary = plistlib.dumps(wf, fmt=plistlib.FMT_BINARY)
    for label, payload in (("plist", xml), ("shortcut", binary)):
        reason = public_template_leak(payload, env)
        if reason:
            print(f"FAIL {label}: {reason}", file=sys.stderr)
            return 1
    plist_path.write_bytes(xml)
    shortcut_path.write_bytes(binary)
    print(f"OK {plist_path} (unsigned template, no token, no host)")
    print(f"OK {shortcut_path} (unsigned; enable Allow Untrusted Shortcuts to import)")
    return 0


def emit_local() -> int:
    env = _load_env()
    token = env.get("PHA_INGEST_TOKEN", "").strip()
    if not token:
        print("FAIL: PHA_INGEST_TOKEN missing in .env", file=sys.stderr)
        return 1
    host_ip = _default_ingest_host()
    port = env.get("PHA_PORT", "8788").strip() or "8788"
    url = f"http://{host_ip}:{port}/ingest/healthkit"
    from pha.healthkit_sync_plan import shortcut_sleep_specs, shortcut_sync_specs
    from pha.wearable_metric_registry import shortcut_pack_version

    pack = shortcut_pack_version()
    sync_specs = shortcut_sync_specs("default")
    sleep_specs = shortcut_sleep_specs("default")
    plan_err = _validate_sync_plan(sync_specs)
    if plan_err:
        print(f"FAIL {plan_err}", file=sys.stderr)
        return 1
    print("sync_plan", [(s.metric_id, s.health_type, s.stat) for s in sync_specs])
    print("sleep_plan", [(s.metric_id, s.unit_health) for s in sleep_specs])
    fact_url = f"http://{host_ip}:{port}/proactive/fact-card?user_id=default"
    fact_view = (
        f"http://{host_ip}:{port}/proactive/fact-card/view"
        f"?user_id=default&token={token}"
    )
    base = f"http://{host_ip}:{port}"
    daily = build_daily(
        base_text=base,
        token_text=token,
        specs=sync_specs,
        sleep_specs=sleep_specs,
        pack_version=pack,
        import_questions=False,
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "endpoint.txt").write_text(
        url + "\n" + fact_url + "\n" + fact_view.split("&token=")[0] + "\n",
        encoding="utf-8",
    )
    jobs = [
        ("pha-ingest-probe", build_probe(url, token), "anyone"),
        ("pha-sync-health", build_health(url, token, sync_specs, pack_version=pack), "people-who-know-me"),
        ("pha-sync-sleep", build_sleep(url, token, sleep_specs, variant="d1"), "people-who-know-me"),
        (
            "pha-sync-sleep-is-today",
            build_sleep(url, token, sleep_specs, variant="is_today"),
            "people-who-know-me",
        ),
        ("pha-fact-card", build_fact_card(fact_url, fact_view, token), "people-who-know-me"),
        ("pha-daily", daily, "people-who-know-me"),
    ]
    for stem, wf, mode in jobs:
        _write_signed(OUT_DIR, stem, wf, mode=mode)
    print(f"endpoint {url}")
    return 0


def _default_ingest_host() -> str:
    override = os.environ.get("PHA_INGEST_URL_HOST", "").strip()
    if override:
        return override
    try:
        name = subprocess.check_output(
            ["scutil", "--get", "LocalHostName"],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        name = ""
    if name:
        return f"{name}.local"
    return "127.0.0.1"


def main() -> int:
    flags = set(sys.argv[1:])
    if "-h" in flags or "--help" in flags:
        print(
            "Build PHA Shortcuts.\n"
            "  (default)     local signed copies → data/local_shortcuts/ (gitignored)\n"
            "  --public      GitHub template → shortcuts/pha-daily.shortcut (no secrets)\n"
            "  --all         local + public\n",
            end="",
        )
        return 0
    unknown = flags - {"--public", "--local", "--all", "-h", "--help"}
    if unknown:
        print(f"Unknown option: {sorted(unknown)}", file=sys.stderr)
        return 2
    want_public = "--public" in flags or "--all" in flags
    want_local = "--local" in flags or "--all" in flags or not want_public
    rc = 0
    if want_local:
        rc = emit_local()
        if rc:
            return rc
    if want_public:
        rc = emit_public()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
