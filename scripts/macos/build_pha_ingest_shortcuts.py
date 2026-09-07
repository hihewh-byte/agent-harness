#!/usr/bin/env python3
"""Build signed Shortcuts for PHA HealthKit ingest (token from .env; output under data/)."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "data" / "local_shortcuts"
OBJ = "\ufffc"


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


def _uuid() -> str:
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


def _output_ref(output_uuid: str, name: str) -> dict:
    return {
        "Value": {
            "OutputName": name,
            "OutputUUID": output_uuid,
            "Type": "ActionOutput",
        },
        "WFSerializationType": "WFTextTokenAttachment",
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


def _workflow(name: str, actions: list[dict]) -> dict:
    return {
        "WFWorkflowActions": actions,
        "WFWorkflowClientVersion": "2700.0.4",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowIcon": _icon(),
        "WFWorkflowImportQuestions": [],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowName": name,
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": [],
    }


def _downloadurl(url: str, token: str, body_uuid: str, body_name: str, action_uuid: str) -> dict:
    return _action(
        "is.workflow.actions.downloadurl",
        {
            "UUID": action_uuid,
            "WFURL": url,
            "WFHTTPMethod": "POST",
            "WFHTTPBodyType": "File",
            "WFHTTPHeaders": _headers(token),
            "WFRequestVariable": _output_ref(body_uuid, body_name),
        },
    )


def _geturl(url: str, token: str, action_uuid: str, out_name: str) -> dict:
    return _action(
        "is.workflow.actions.downloadurl",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFURL": url,
            "WFHTTPMethod": "GET",
            "WFHTTPHeaders": _headers(token),
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


def _make_url(url: str, action_uuid: str, name: str) -> dict:
    """Create a URL item. Open URLs cannot take a raw WFURL string (shows「无 URL」)."""
    return _action(
        "is.workflow.actions.url",
        {
            "UUID": action_uuid,
            "CustomOutputName": name,
            "WFURLActionURL": url,
        },
    )


def _openurl(src_uuid: str, src_name: str) -> dict:
    return _action(
        "is.workflow.actions.openurl",
        {"WFInput": _output_ref(src_uuid, src_name)},
    )


def build_fact_card(url: str, view_url: str, token: str) -> dict:
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
) -> dict:
    """Today's samples of one Health type. Only this type is requested from Health."""
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
                        {
                            "Bounded": True,
                            "Operator": 1002,
                            "Property": "Start Date",
                            "Removable": False,
                            "Values": {"Number": "7", "Unit": 16},
                        },
                    ],
                },
                "WFSerializationType": "WFContentPredicateTableTemplate",
            },
    }
    # Find picker label must be registry shortcut_health_type (Active Calories,
    # not Active Energy). Only set the unit that already works on device (RHR).
    if unit == "count/min":
        params["WFHealthActionUnit"] = unit
    return _action("is.workflow.actions.filter.health.quantity", params)


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


def _sync_one_metric(url: str, token: str, spec) -> tuple[list[dict], str, str, str, str]:
    """Same chain as the working steps shortcut: Find → Value → Numbers → Stat → one POST."""
    find_id = _uuid()
    val_id = _uuid()
    num_id = _uuid()
    stat_id = _uuid()
    plain_id = _uuid()
    text_id = _uuid()
    json_id = _uuid()
    resp_id = _uuid()
    samples_name = f"{spec.metric_id} Samples"
    value_name = f"{spec.metric_id} Value"
    numbers_name = f"{spec.metric_id} Numbers"
    stat_name = f"{spec.metric_id} Stat"
    plain_name = f"{spec.metric_id} Number"
    text_name = f"{spec.metric_id} Text"
    json_name = f"{spec.metric_id} JSON"
    resp_name = f"{spec.metric_id} Response"
    post = _downloadurl(url, token, json_id, json_name, resp_id)
    post["WFWorkflowActionParameters"]["CustomOutputName"] = resp_name
    unit = spec.unit_health or spec.unit or "count"
    actions = [
        _find_health(spec.health_type, find_id, samples_name, unit=unit),
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
                        '{"user_id":"default","samples":[{"metric_type":"',
                        spec.ingest_key,
                        '","timestamp":"","value":"',
                        (text_id, text_name),
                        '","unit":"',
                        spec.unit,
                        '","source":"healthkit"}]}',
                    ]
                ),
            },
        ),
        post,
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
    url: str,
    token: str,
    specs: list,
    *,
    variant: str = "d1",
    limit: int = 150,
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
                                "当前勾选没有可同步的睡眠分期。"
                                "请在完整卡勾选睡眠总时长或深睡后，在 Mac 上重新生成本捷径。",
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
    actions = [
        _find_sleep(find_id, "Sleep Samples", variant=variant, limit=limit),
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
        ),
    ]
    return _workflow(name, actions)


def build_health(url: str, token: str, specs: list) -> dict:
    """iPhone-only: one POST per selected quantity metric (do not POST Health items)."""
    if not specs:
        return _workflow(
            "PHA 同步健康",
            [
                _action(
                    "is.workflow.actions.showresult",
                    {
                        "Text": _text_with_refs(
                            [
                                "当前勾选的指标没有可按日合计的 Health 数量类型。"
                                "请在完整卡勾选步数、活动消耗或静息心率后，在 Mac 上重新生成本捷径。",
                            ]
                        )
                    },
                )
            ],
        )
    actions: list[dict] = []
    result_parts: list[str | tuple[str, str]] = []
    for spec in specs:
        block, stat_id, stat_name, resp_id, resp_name = _sync_one_metric(url, token, spec)
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
    actions.append(
        _action(
            "is.workflow.actions.showresult",
            {"Text": _text_with_refs(result_parts)},
        )
    )
    return _workflow("PHA 同步健康", actions)


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
    env = _load_env()
    token = env.get("PHA_INGEST_TOKEN", "").strip()
    if not token:
        print("FAIL: PHA_INGEST_TOKEN missing in .env", file=sys.stderr)
        return 1
    host_ip = _default_ingest_host()
    port = env.get("PHA_PORT", "8788").strip() or "8788"
    url = f"http://{host_ip}:{port}/ingest/healthkit"
    from pha.healthkit_sync_plan import shortcut_sleep_specs, shortcut_sync_specs

    sync_specs = shortcut_sync_specs("default")
    sleep_specs = shortcut_sleep_specs("default")
    print(
        "sync_plan",
        [(s.metric_id, s.health_type, s.stat) for s in sync_specs],
    )
    print(
        "sleep_plan",
        [(s.metric_id, s.unit_health) for s in sleep_specs],
    )
    fact_url = f"http://{host_ip}:{port}/proactive/fact-card?user_id=default"
    fact_view = (
        f"http://{host_ip}:{port}/proactive/fact-card/view"
        f"?user_id=default&token={token}"
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "endpoint.txt").write_text(
        url + "\n" + fact_url + "\n" + fact_view.split("&token=")[0] + "\n",
        encoding="utf-8",
    )

    jobs = [
        ("pha-ingest-probe", build_probe(url, token), "anyone"),
        ("pha-sync-health", build_health(url, token, sync_specs), "people-who-know-me"),
        ("pha-sync-sleep", build_sleep(url, token, sleep_specs, variant="d1"), "people-who-know-me"),
        (
            "pha-sync-sleep-is-today",
            build_sleep(url, token, sleep_specs, variant="is_today"),
            "people-who-know-me",
        ),
        ("pha-fact-card", build_fact_card(fact_url, fact_view, token), "people-who-know-me"),
    ]
    for stem, wf, mode in jobs:
        xml_path = OUT_DIR / f"{stem}.plist"
        unsigned_path = OUT_DIR / f"{stem}.unsigned.shortcut"
        signed_path = OUT_DIR / f"{stem}.shortcut"
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
        print(f"OK {signed_path}")
    print(f"endpoint {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
