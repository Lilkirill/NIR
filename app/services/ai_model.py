from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceSignal:
    name: str
    weight: float
    category: str


class ConfigGuardQwenAdvisor:
    """Qwen2.5-based LLM advisor for network configuration validation.

    The class supports two execution modes:

    * ``mock`` (default) — deterministic domain adapter that does not require
      PyTorch, GPU, internet or downloaded model weights. This mode is used by
      tests and by the default Docker environment.
    * ``local_llm`` — loads a local HuggingFace-compatible Qwen2.5-3B-Instruct
      model and, optionally, a LoRA adapter. This mode is enabled through
      environment variables and is intended for the diploma experiment where the
      model is fine-tuned on the bundled JSONL training data.

    Environment variables:
        CONFIGGUARD_AI_MODE=mock|local_llm
        QWEN_MODEL_PATH=Qwen/Qwen2.5-3B-Instruct or local directory
        QWEN_ADAPTER_PATH=./models/configguard-qwen-lora (optional)
        QWEN_MAX_NEW_TOKENS=700
    """

    model_name = 'ConfigGuard-Qwen2.5-3B-Instruct-Advisor'
    model_version = '2.0'
    model_type = 'fine_tunable_local_llm_advisor'
    base_model = 'Qwen/Qwen2.5-3B-Instruct'

    def __init__(
        self,
        *,
        mode: str | None = None,
        model_path: str | None = None,
        adapter_path: str | None = None,
        max_new_tokens: int | None = None,
    ) -> None:
        self.mode = (mode or os.getenv('CONFIGGUARD_AI_MODE') or 'mock').strip().lower()
        self.model_path = model_path or os.getenv('QWEN_MODEL_PATH') or self.base_model
        self.adapter_path = adapter_path or os.getenv('QWEN_ADAPTER_PATH') or None
        self.max_new_tokens = max_new_tokens or int(os.getenv('QWEN_MAX_NEW_TOKENS', '700'))
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._load_error: str | None = None

        if self.mode == 'local_llm':
            self._lazy_load_local_model()

    def analyze(
        self,
        *,
        vendor: str,
        hostname: str,
        config_text: str,
        normalized_config: dict[str, Any],
        findings: list[dict[str, Any]],
        validation_status: str,
    ) -> dict[str, Any]:
        signals = self._extract_signals(config_text=config_text, normalized_config=normalized_config)
        prompt_messages = self._build_messages(
            vendor=vendor,
            hostname=hostname,
            config_text=config_text,
            normalized_config=normalized_config,
            findings=findings,
            validation_status=validation_status,
            signals=signals,
        )

        if self.mode == 'local_llm' and self._model is not None and self._tokenizer is not None:
            generated = self._generate_with_qwen(prompt_messages)
            parsed = self._parse_model_json(generated)
            if parsed:
                return self._normalize_llm_payload(
                    parsed,
                    vendor=vendor,
                    hostname=hostname,
                    signals=signals,
                    prompt_messages=prompt_messages,
                    generated_text=generated,
                )

        return self._deterministic_analysis(
            vendor=vendor,
            hostname=hostname,
            normalized_config=normalized_config,
            findings=findings,
            validation_status=validation_status,
            signals=signals,
            prompt_messages=prompt_messages,
        )

    def _lazy_load_local_model(self) -> None:
        try:
            import torch  # type: ignore
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map='auto',
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                trust_remote_code=True,
            )
            if self.adapter_path:
                from peft import PeftModel  # type: ignore

                self._model = PeftModel.from_pretrained(self._model, self.adapter_path)
            self._model.eval()
        except Exception as exc:  # pragma: no cover - optional runtime path
            self._load_error = str(exc)
            self._tokenizer = None
            self._model = None

    def _generate_with_qwen(self, messages: list[dict[str, str]]) -> str:
        import torch  # type: ignore

        tokenizer = self._tokenizer
        model = self._model
        if tokenizer is None or model is None:  # pragma: no cover
            return ''

        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors='pt').to(model.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=0.0,
                eos_token_id=tokenizer.eos_token_id,
            )
        generated_ids = output_ids[0][inputs.input_ids.shape[-1]:]
        return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    def _deterministic_analysis(
        self,
        *,
        vendor: str,
        hostname: str,
        normalized_config: dict[str, Any],
        findings: list[dict[str, Any]],
        validation_status: str,
        signals: list[EvidenceSignal],
        prompt_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        context_score, context_state = self._context_score(signals)
        symbolic_score, factors = self._symbolic_score(normalized_config=normalized_config, findings=findings)
        status_penalty = 0.12 if validation_status == 'failed' else -0.04
        risk_score = self._clamp((context_score * 0.30) + (symbolic_score * 0.70) + status_penalty, 0.0, 1.0)
        risk_level = self._risk_level(risk_score)
        predicted_failure_kind = self._predict_failure_kind(factors=factors, findings=findings, risk_level=risk_level)
        recommendations = self._recommendations(factors=factors, findings=findings, risk_level=risk_level)
        confidence = self._confidence(signals=signals, findings=findings, normalized_config=normalized_config)
        explanation = self._explain(
            vendor=vendor,
            hostname=hostname,
            risk_level=risk_level,
            risk_score=risk_score,
            factors=factors,
            context_state=context_state,
        )
        prompt_preview = self._messages_to_prompt(prompt_messages)

        return {
            'model_name': self.model_name,
            'model_version': self.model_version,
            'model_type': self.model_type,
            'base_model': self.base_model,
            'execution_mode': self.mode,
            'fine_tuning_method': 'LoRA/QLoRA supervised fine-tuning',
            'training_dataset': 'data/llm_training/configguard_qwen_train.jsonl',
            'objective': 'LLM-анализ результатов формальной валидации конфигураций: риск, причина отказа, объяснение и рекомендации.',
            'vendor': vendor,
            'hostname': hostname,
            'risk_score': round(risk_score, 3),
            'risk_level': risk_level,
            'predicted_failure_kind': predicted_failure_kind,
            'confidence': confidence,
            'llm_prompt_preview': prompt_preview[:1600],
            'evidence_signals': [signal.name for signal in signals[:50]],
            'evidence_signals_total': len(signals),
            'context_state': {key: round(value, 3) for key, value in context_state.items()},
            'key_factors': factors,
            'explanation': explanation,
            'recommendations': recommendations,
            'local_model_load_error': self._load_error,
            'replacement_ready': True,
            'integration_note': (
                'Компонент переведён на архитектуру ConfigGuard-Qwen2.5-3B-Instruct-Advisor. '
                'По умолчанию используется устойчивый mock-режим для тестов и Docker. При установке '
                'optional LLM-зависимостей, загрузке Qwen2.5-3B-Instruct и указании CONFIGGUARD_AI_MODE=local_llm '
                'тот же контракт API выполняется локальной дообучаемой Qwen-моделью.'
            ),
        }

    def _normalize_llm_payload(
        self,
        payload: dict[str, Any],
        *,
        vendor: str,
        hostname: str,
        signals: list[EvidenceSignal],
        prompt_messages: list[dict[str, str]],
        generated_text: str,
    ) -> dict[str, Any]:
        risk_score = self._clamp(float(payload.get('risk_score', 0.5)), 0.0, 1.0)
        risk_level = str(payload.get('risk_level') or self._risk_level(risk_score))
        allowed_levels = {'minimal', 'low', 'medium', 'high', 'critical'}
        if risk_level not in allowed_levels:
            risk_level = self._risk_level(risk_score)
        recommendations = payload.get('recommendations') or []
        if not isinstance(recommendations, list):
            recommendations = [str(recommendations)]
        key_factors = payload.get('key_factors') or []
        if not isinstance(key_factors, list):
            key_factors = [{'code': 'LLM_FACTOR', 'message': str(key_factors), 'category': 'llm', 'weight': 0.1}]
        return {
            'model_name': self.model_name,
            'model_version': self.model_version,
            'model_type': self.model_type,
            'base_model': self.base_model,
            'execution_mode': 'local_llm',
            'fine_tuning_method': 'LoRA/QLoRA supervised fine-tuning',
            'training_dataset': 'data/llm_training/configguard_qwen_train.jsonl',
            'vendor': vendor,
            'hostname': hostname,
            'risk_score': round(risk_score, 3),
            'risk_level': risk_level,
            'predicted_failure_kind': str(payload.get('predicted_failure_kind') or 'needs_review'),
            'confidence': round(self._clamp(float(payload.get('confidence', 0.75)), 0.0, 1.0), 3),
            'key_factors': key_factors[:12],
            'explanation': str(payload.get('explanation') or generated_text[:600]),
            'recommendations': [str(item) for item in recommendations[:8]],
            'llm_prompt_preview': self._messages_to_prompt(prompt_messages)[:1600],
            'raw_model_response': generated_text[:2500],
            'evidence_signals': [signal.name for signal in signals[:50]],
            'evidence_signals_total': len(signals),
            'replacement_ready': False,
        }

    @staticmethod
    def _parse_model_json(text: str) -> dict[str, Any] | None:
        text = text.strip()
        candidates = [text]
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL)
        if match:
            candidates.append(match.group(1))
        match = re.search(r'(\{.*\})', text, flags=re.DOTALL)
        if match:
            candidates.append(match.group(1))
        for candidate in candidates:
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return value
            except Exception:
                continue
        return None

    def _extract_signals(self, *, config_text: str, normalized_config: dict[str, Any]) -> list[EvidenceSignal]:
        signals: list[EvidenceSignal] = []
        lines = [line.strip().lower() for line in config_text.splitlines() if line.strip() and line.strip() != '!']
        patterns: list[tuple[str, str, float, str]] = [
            (r'^(hostname|sysname|set system host-name)\b', 'hostname_present', -0.12, 'completeness'),
            (r'^(interface|/interface|set interfaces)\b', 'interface_block', -0.03, 'completeness'),
            (r'(ip address|address\s+\d+\.\d+\.\d+\.\d+|/ip address)', 'ip_address_present', -0.04, 'completeness'),
            (r'(ip route 0\.0\.0\.0|route 0\.0\.0\.0/0|dst-address=0\.0\.0\.0/0|ip route-static 0\.0\.0\.0)', 'default_route_present', -0.11, 'routing'),
            (r'(transport input ssh|services ssh|stelnet server enable|ssh server|/ip service.*ssh)', 'ssh_present', -0.14, 'security'),
            (r'(transport input telnet|telnet server enable|/ip service.*telnet.*disabled=no)', 'telnet_exposed', 0.18, 'security'),
            (r'^(username|set system login user|/user add|local-user)\b', 'local_user_present', -0.08, 'access'),
            (r'(password 0|secret 0|plain-text-password|password=)', 'weak_secret_signal', 0.12, 'security'),
            (r'\bshutdown\b|disable=yes', 'disabled_interface', 0.04, 'completeness'),
            (r'\b(router ospf|protocols ospf|router bgp|protocols bgp)\b', 'dynamic_routing', -0.03, 'routing'),
            (r'\b(access-list|firewall filter|acl)\b', 'access_policy', -0.02, 'security'),
            (r'(aaa new-model|radius-server|tacacs-server)', 'aaa_present', -0.06, 'access'),
        ]
        for line in lines:
            for pattern, signal_name, weight, category in patterns:
                if re.search(pattern, line):
                    signals.append(EvidenceSignal(signal_name, weight, category))

        if not normalized_config.get('interfaces'):
            signals.append(EvidenceSignal('missing_interfaces', 0.22, 'completeness'))
        if not normalized_config.get('routes'):
            signals.append(EvidenceSignal('missing_routes', 0.10, 'routing'))
        if not normalized_config.get('users'):
            signals.append(EvidenceSignal('missing_users', 0.09, 'access'))
        if not normalized_config.get('services', {}).get('ssh_enabled'):
            signals.append(EvidenceSignal('missing_ssh', 0.18, 'security'))
        return signals

    def _context_score(self, signals: list[EvidenceSignal]) -> tuple[float, dict[str, float]]:
        state = {'security': 0.0, 'routing': 0.0, 'completeness': 0.0, 'access': 0.0}
        memory = dict(state)
        for idx, signal in enumerate(signals):
            decay = 0.80 + min(idx, 10) * 0.008
            update = 1.0 - decay + 0.10
            previous = memory.get(signal.category, 0.0)
            memory[signal.category] = (decay * previous) + (update * signal.weight)
            state[signal.category] = math.tanh(memory[signal.category])
        raw = 0.40
        raw += state['security'] * 0.36
        raw += state['routing'] * 0.23
        raw += state['completeness'] * 0.24
        raw += state['access'] * 0.18
        return self._clamp(raw, 0.0, 1.0), state

    def _symbolic_score(self, *, normalized_config: dict[str, Any], findings: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
        score = 0.18
        factors: list[dict[str, Any]] = []

        def add(code: str, weight: float, message: str, category: str) -> None:
            nonlocal score
            score += weight
            factors.append({'code': code, 'weight': round(weight, 3), 'category': category, 'message': message})

        for finding in findings:
            severity = finding.get('severity')
            if severity == 'error':
                add(str(finding.get('code', 'ERROR')), 0.16, str(finding.get('message', 'Ошибка правила')), str(finding.get('category') or 'policy'))
            else:
                add(str(finding.get('code', 'WARNING')), 0.07, str(finding.get('message', 'Предупреждение правила')), str(finding.get('category') or 'policy'))

        services = normalized_config.get('services', {}) or {}
        interfaces = normalized_config.get('interfaces', []) or []
        routes = normalized_config.get('routes', []) or []
        users = normalized_config.get('users', []) or []
        addressed = sum(1 for item in interfaces if item.get('addresses'))
        enabled_without_ip = [item.get('name') for item in interfaces if item.get('enabled') and not item.get('addresses')]

        if not services.get('ssh_enabled'):
            add('AI_MISSING_SSH', 0.15, 'Не найден признак защищённого удалённого доступа SSH.', 'security')
        if not any(route.get('destination') == '0.0.0.0/0' for route in routes):
            add('AI_NO_DEFAULT_ROUTE', 0.10, 'Не найден маршрут по умолчанию.', 'routing')
        if not users:
            add('AI_NO_LOCAL_USERS', 0.08, 'Не найдены локальные учётные записи.', 'access')
        if interfaces and addressed / max(len(interfaces), 1) < 0.5:
            add('AI_LOW_ADDRESS_COVERAGE', 0.09, 'Менее половины интерфейсов содержит адресацию.', 'completeness')
        if enabled_without_ip:
            add('AI_ENABLED_INTERFACES_WITHOUT_IP', 0.06, f'Включённые интерфейсы без адресации: {", ".join(map(str, enabled_without_ip[:3]))}.', 'completeness')

        if services.get('ssh_enabled'):
            score -= 0.05
        if users:
            score -= 0.03
        if routes:
            score -= 0.03
        if interfaces and addressed == len(interfaces):
            score -= 0.04
        return self._clamp(score, 0.0, 1.0), factors[:12]

    @staticmethod
    def _predict_failure_kind(*, factors: list[dict[str, Any]], findings: list[dict[str, Any]], risk_level: str) -> str:
        if not factors and risk_level in {'low', 'minimal'}:
            return 'passed_with_low_risk'
        categories = [str(item.get('category') or '') for item in factors]
        codes = [str(item.get('code') or '') for item in findings] + [str(item.get('code') or '') for item in factors]
        if any('schema' in code.lower() for code in codes):
            return 'failed_schema'
        if categories.count('security') >= 2:
            return 'failed_security_policy'
        if categories.count('routing') >= 1:
            return 'failed_routing_policy'
        if categories.count('completeness') >= 1:
            return 'failed_incomplete_configuration'
        return 'failed_policy' if risk_level in {'high', 'critical'} else 'needs_review'

    @staticmethod
    def _recommendations(*, factors: list[dict[str, Any]], findings: list[dict[str, Any]], risk_level: str) -> list[str]:
        recs: list[str] = []
        for finding in findings:
            recommendation = finding.get('recommendation')
            if recommendation:
                recs.append(str(recommendation))
        factor_codes = {str(item.get('code')) for item in factors}
        if 'AI_MISSING_SSH' in factor_codes:
            recs.append('Включить SSH и запретить незащищённые протоколы удалённого доступа.')
        if 'AI_NO_DEFAULT_ROUTE' in factor_codes:
            recs.append('Проверить роль устройства и при необходимости добавить маршрут по умолчанию.')
        if 'AI_NO_LOCAL_USERS' in factor_codes:
            recs.append('Добавить локальную административную учётную запись или явно описать внешний контур AAA.')
        if 'AI_LOW_ADDRESS_COVERAGE' in factor_codes or 'AI_ENABLED_INTERFACES_WITHOUT_IP' in factor_codes:
            recs.append('Проверить полноту интерфейсных секций и адресацию включённых интерфейсов.')
        if risk_level in {'high', 'critical'}:
            recs.append('Перед внедрением отправить конфигурацию на повторную проверку после исправления критичных факторов.')
        return list(dict.fromkeys(recs))[:8]

    @staticmethod
    def _confidence(*, signals: list[EvidenceSignal], findings: list[dict[str, Any]], normalized_config: dict[str, Any]) -> float:
        coverage = 0.45
        if signals:
            coverage += min(len(signals), 20) / 100
        if findings:
            coverage += 0.15
        if normalized_config.get('interfaces'):
            coverage += 0.10
        if normalized_config.get('hostname'):
            coverage += 0.05
        return round(ConfigGuardQwenAdvisor._clamp(coverage, 0.35, 0.92), 3)

    @staticmethod
    def _explain(*, vendor: str, hostname: str, risk_level: str, risk_score: float, factors: list[dict[str, Any]], context_state: dict[str, float]) -> str:
        if factors:
            top = ', '.join(str(item['code']) for item in factors[:3])
            return (
                f'Qwen-ассистент оценил конфигурацию {vendor}/{hostname} как {risk_level} '
                f'(score={risk_score:.3f}). Основной вклад дали факторы: {top}. '
                f'Контекстные признаки: security={context_state.get("security", 0):.2f}, '
                f'routing={context_state.get("routing", 0):.2f}, completeness={context_state.get("completeness", 0):.2f}.'
            )
        return f'Qwen-ассистент не обнаружил выраженных риск-факторов для {vendor}/{hostname}; риск {risk_level} (score={risk_score:.3f}).'

    def _build_messages(
        self,
        *,
        vendor: str,
        hostname: str,
        config_text: str,
        normalized_config: dict[str, Any],
        findings: list[dict[str, Any]],
        validation_status: str,
        signals: list[EvidenceSignal],
    ) -> list[dict[str, str]]:
        findings_preview = [
            {
                'code': item.get('code'),
                'severity': item.get('severity'),
                'category': item.get('category'),
                'message': item.get('message'),
                'recommendation': item.get('recommendation'),
            }
            for item in findings[:12]
        ]
        feature_summary = {
            'interfaces_total': len(normalized_config.get('interfaces', []) or []),
            'routes_total': len(normalized_config.get('routes', []) or []),
            'users_total': len(normalized_config.get('users', []) or []),
            'ssh_enabled': bool((normalized_config.get('services') or {}).get('ssh_enabled')),
            'signals': [signal.name for signal in signals[:30]],
        }
        config_excerpt = config_text[:3500]
        system = (
            'Ты ConfigGuard-Qwen2.5-3B-Instruct-Advisor — LLM-ассистент сетевого администратора. '
            'Работай только поверх предоставленных фактов: исходной конфигурации, нормализованной модели и findings. '
            'Не выдумывай команды, если данных недостаточно. Верни строго JSON без markdown.'
        )
        user = {
            'task': 'Проанализируй результат формальной валидации сетевой конфигурации.',
            'required_json_schema': {
                'risk_score': 'float 0..1',
                'risk_level': 'minimal|low|medium|high|critical',
                'predicted_failure_kind': 'passed_with_low_risk|failed_security_policy|failed_routing_policy|failed_incomplete_configuration|failed_schema|failed_policy|needs_review',
                'confidence': 'float 0..1',
                'key_factors': [{'code': 'string', 'category': 'string', 'weight': 'float', 'message': 'string'}],
                'explanation': 'string in Russian',
                'recommendations': ['string in Russian'],
            },
            'vendor': vendor,
            'hostname': hostname,
            'validation_status': validation_status,
            'feature_summary': feature_summary,
            'findings': findings_preview,
            'normalized_config': normalized_config,
            'config_excerpt': config_excerpt,
        }
        return [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)}]

    @staticmethod
    def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
        return '\n\n'.join(f"{item['role'].upper()}: {item['content']}" for item in messages)

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 0.78:
            return 'critical'
        if score >= 0.55:
            return 'high'
        if score >= 0.32:
            return 'medium'
        if score >= 0.16:
            return 'low'
        return 'minimal'

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))


# Backward-compatible alias for older imports/tests.
ConfigLLMAdvisor = ConfigGuardQwenAdvisor
