"""Testa HunyuanService no namespace `hunyuan` v20230901 (SDK intl-en).

Causa raiz do InterfaceNotExist: a conta é Tencent Cloud International, onde
o Hunyuan 3D vive em `hunyuan` v20230901 — não em `ai3d` v20250513 (mainland).

O cliente SDK é mockado (fronteira externa) via _get_client. Não há rede.
"""
import types

import pytest

from services.hunyuan import HunyuanService


def _file3d(type_, url):
    return types.SimpleNamespace(Type=type_, Url=url, PreviewImageUrl=None)


class _FakeClient:
    def __init__(self, submit_resp=None, query_resp=None):
        self._submit_resp = submit_resp
        self._query_resp = query_resp
        self.captured = {}

    def SubmitHunyuanTo3DProJob(self, req):
        self.captured["submit_req"] = req
        return self._submit_resp

    def QueryHunyuanTo3DProJob(self, req):
        self.captured["query_req"] = req
        return self._query_resp


def _service_with(monkeypatch, fake) -> HunyuanService:
    svc = HunyuanService()
    monkeypatch.setattr(svc, "_get_client", lambda: fake)
    return svc


@pytest.mark.asyncio
async def test_submit_generation_with_prompt_returns_job_id(monkeypatch):
    fake = _FakeClient(submit_resp=types.SimpleNamespace(JobId="job-123", RequestId="r"))
    svc = _service_with(monkeypatch, fake)

    job_id = await svc.submit_generation(prompt="um gato minimalista")

    assert job_id == "job-123"
    assert fake.captured["submit_req"].Prompt == "um gato minimalista"


@pytest.mark.asyncio
async def test_submit_generation_with_image_base64(monkeypatch):
    fake = _FakeClient(submit_resp=types.SimpleNamespace(JobId="job-9", RequestId="r"))
    svc = _service_with(monkeypatch, fake)

    job_id = await svc.submit_generation(image_base64="QUJD")

    assert job_id == "job-9"
    assert fake.captured["submit_req"].ImageBase64 == "QUJD"


@pytest.mark.asyncio
async def test_check_status_done_maps_to_finished_with_glb_url(monkeypatch):
    resp = types.SimpleNamespace(
        Status="DONE",
        ErrorCode=None,
        ErrorMessage=None,
        ResultFile3Ds=[
            _file3d("OBJ", "https://t/model.obj"),
            _file3d("GLB", "https://t/model.glb"),
        ],
        RequestId="r",
    )
    svc = _service_with(monkeypatch, _FakeClient(query_resp=resp))

    out = await svc.check_status("job-1")

    assert out["status"] == "FINISHED"
    assert out["model_url"] == "https://t/model.glb"


@pytest.mark.asyncio
async def test_check_status_running_has_no_url_no_error(monkeypatch):
    resp = types.SimpleNamespace(
        Status="RUN", ErrorCode=None, ErrorMessage=None,
        ResultFile3Ds=None, RequestId="r",
    )
    svc = _service_with(monkeypatch, _FakeClient(query_resp=resp))

    out = await svc.check_status("job-1")

    assert out["status"] == "RUN"
    assert out.get("model_url") is None
    assert out.get("error_code") is None


@pytest.mark.asyncio
async def test_check_status_fail_surfaces_error(monkeypatch):
    resp = types.SimpleNamespace(
        Status="FAIL", ErrorCode="InternalError",
        ErrorMessage="geração falhou", ResultFile3Ds=None, RequestId="r",
    )
    svc = _service_with(monkeypatch, _FakeClient(query_resp=resp))

    out = await svc.check_status("job-1")

    assert out["error_code"] == "InternalError"
    assert out["error_message"] == "geração falhou"
