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


def build_fact_card(url: str, token: str) -> dict:
    """GET fact card JSON → iPhone local notification (no HealthKit, no LLM)."""
    get_id = _uuid()
    note_id = _uuid()
    title_id = _uuid()
    body_id = _uuid()
    actions = [
        _geturl(url, token, get_id, "Fact Card"),
        _dict_value(get_id, "Fact Card", "notification", note_id, "Notification"),
        _dict_value(note_id, "Notification", "title", title_id, "Title"),
        _dict_value(note_id, "Notification", "body", body_id, "Body"),
        _action(
            "is.workflow.actions.notification",
            {
                "WFNotificationActionTitle": _text_with_refs([(title_id, "Title")]),
                "WFNotificationActionBody": _text_with_refs([(body_id, "Body")]),
            },
        ),
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


def _find_health(sample_type: str, action_uuid: str) -> dict:
    """Today's samples of one Health type. Only this type is requested from Health."""
    return _action(
        "is.workflow.actions.filter.health.quantity",
        {
            "UUID": action_uuid,
            "CustomOutputName": "Health Samples",
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


def _statistics_sum(src_uuid: str, src_name: str, action_uuid: str, out_name: str) -> dict:
    ref = _output_ref(src_uuid, src_name)
    return _action(
        "is.workflow.actions.statistics",
        {
            "UUID": action_uuid,
            "CustomOutputName": out_name,
            "WFStatisticsOperation": "Sum",
            "Input": ref,
            "WFInput": ref,
        },
    )


def build_health(url: str, token: str) -> dict:
    """iPhone-only: today's Steps sum as one JSON number (do not POST Health items)."""
    find_id = _uuid()
    val_id = _uuid()
    num_id = _uuid()
    sum_id = _uuid()
    text_id = _uuid()
    json_id = _uuid()
    url_id = _uuid()
    actions = [
        _find_health("Steps", find_id),
        _get_detail(find_id, "Health Samples", "Value", val_id, "Steps Value"),
        _detect_number(val_id, "Steps Value", num_id, "Steps Numbers"),
        _statistics_sum(num_id, "Steps Numbers", sum_id, "Steps Sum"),
        _action(
            "is.workflow.actions.gettext",
            {
                "UUID": text_id,
                "CustomOutputName": "Steps Text",
                "WFTextActionText": _text_with_refs([(sum_id, "Steps Sum")]),
            },
        ),
        _action(
            "is.workflow.actions.gettext",
            {
                "UUID": json_id,
                "CustomOutputName": "JSON",
                "WFTextActionText": _text_with_refs(
                    [
                        '{"user_id":"default","samples":[{"metric_type":"steps","timestamp":"","value":"',
                        (text_id, "Steps Text"),
                        '","unit":"count","source":"healthkit"}]}',
                    ]
                ),
            },
        ),
        _downloadurl(url, token, json_id, "JSON", url_id),
        _action(
            "is.workflow.actions.showresult",
            {
                "Text": _text_with_refs(
                    [
                        "今日步数合计：",
                        (sum_id, "Steps Sum"),
                        "\n服务器：",
                        (url_id, "Contents of URL"),
                    ]
                )
            },
        ),
    ]
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
    fact_url = f"http://{host_ip}:{port}/proactive/fact-card?user_id=default"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "endpoint.txt").write_text(url + "\n" + fact_url + "\n", encoding="utf-8")

    jobs = [
        ("pha-ingest-probe", build_probe(url, token), "anyone"),
        ("pha-sync-health", build_health(url, token), "people-who-know-me"),
        ("pha-fact-card", build_fact_card(fact_url, token), "people-who-know-me"),
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
