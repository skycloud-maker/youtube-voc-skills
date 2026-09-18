# VoC 데이터사전 v3.0 — 66컬럼 정의 · Enum 허용값

> 원본: `15_VoC_데이터사전_스키마_v3.0_66컬럼.xlsx`
> 정본 `21_결과파일_점검_기준문서_v4.5` §0-1 이 요구하는 필수 첨부 ③ 이다
> 컬럼 정의와 허용값만 추출했다. Scoring 기준·판정 규칙은 정본 §10 에 있다

---

# 1. 66컬럼 정의

| # | 컬럼명 | 레이어 | 종류 | 정의 | 값·예시 |
|---:|---|---|---|---|---|
| 1 | source_id | 식별자 | 메타 | 댓글 고유 ID | (ID) |
| 2 | raw_row_index | 식별자 | 메타 | 원본 행 번호 | 정수 |
| 3 | parent_voc_id | 관계 | 중간값 | 부모 댓글 ID | (ID) 또는 공백 |
| 4 | comment_relation | 관계 | 중간값 | 부모/답글 구분 | parent / reply |
| 5 | atomic_id | Atomic | 메타 | 분리 단위 식별자 | source_id-01 형식 |
| 6 | atomic_index | Atomic | 메타 | 분리 순번(상한 없음) | 01, 02, 03 … |
| 7 | original_voc | 원문 | 최종값 | 원문 댓글 | 텍스트 |
| 8 | voc_cleaned | 정제 | 중간값 | NFC·제어문자 제거·공백 정리만 적용한 source 원문 정제본. 이모지·반복부호·@호출명·인사말은 원형 보존 | 텍스트 |
| 9 | voc_residual | 분리 | 중간값 | 분리 단계에서 어느 atomic_voc에도 포함되지 않은 원문 잔여 텍스트. 정제 단계 산출물이 아니며, @호출명·인사말·이모지·감탄사·채널 칭찬 등을 삭제하지 않고 source 단위로 형제 atomic 전원에 동일 복사 | 텍스트(미사용 span의 원문 순서 결합) |
| 10 | atomic_voc | Atomic | 최종값 | 독립 분석결과 단위의 원문 발췌. voc_cleaned의 실제 span이며 형제 간 중복 금지 | 텍스트(발췌) |
| 11 | atomic_voc_summary | Atomic | 중간값 | Topic 판단용 요약 (←현 atomic_voc) | 텍스트 |
| 12 | topic_provisional | 주제 | 자유서술 | 주제 추출 단계에서 해당 atomic의 내용·조건·근거를 설명하는 자유 서술. 캐노니컬 라벨을 그대로 반복하지 않는다. 분리·중복 판정용 provisional_label은 내부값·trace에만 기록한다. | 자유 텍스트(한두 문장) |
| 13 | topic | 주제 | 최종값 | atomic 전체판정 LLM이 제안하고 엔진이 정규화·근거 가드로 확정하는 최종 주제 라벨 | 캐노니컬 목록 · 미분류 · N/A |
| 14 | topic_evidence | 주제 | 근거 | 주제 판단 근거·차수 | 텍스트 |
| 15 | topic_score | 주제(Scoring) | 점수 | ★인사이트 가치 | 0·1·3·5 (0=N/A … 5=상품기획 인사이트) |
| 16 | reference_brand | 관점 | 메타 | 자사 기준 브랜드(극성 정규화 기준) | LG (고정) |
| 17 | product_tags | 제품(자사) | 최종값 | 자사 제품 태그(자사 정보만) | 태그[] |
| 18 | product_additional_info | 제품(자사) | 최종값 | 자사 부가정보(모델/라인업/팻네임 등, 자사만) | 태그[] |
| 19 | competitor_brand_tags | 경쟁사 | 최종값 | 경쟁 브랜드명 | 태그[] |
| 20 | competitor_product_tags | 경쟁사 | 최종값 | 경쟁사 제품 태그(미러) | 태그[] |
| 21 | competitor_product_additional_info | 경쟁사 | 최종값 | 경쟁사 부가정보(미러) | 태그[] |
| 22 | brand | 브랜드 | 최종값 | 원문 표기 브랜드 | 텍스트 |
| 23 | market | 시장 | 최종값 | 시장(국가) | KR 등 |
| 24 | language | 언어 | 최종값 | 언어 | 한국어 등 |
| 25 | cej | CEJ | 최종값 | 고객 여정 단계. 이슈가 속한 단계 기준(R11). 사용준비 vs 사용은 R15 | 인지·탐색·결정·구매·배송·사용준비·사용·관리·교체 · 해당없음 (설치 금지 → 사용준비로 매핑) |
| 26 | cej_evidence | CEJ | 근거 | CEJ 판단 근거 | 텍스트 |
| 27 | inquiry_flag | Inquiry | 최종값 | 문의 여부 | Y / N |
| 28 | inquiry_type | Inquiry | 최종값 | 문의 유형(정규 enum). 원 출력은 inquiry_type_raw에 보존 | (값 목록 시트 참조) — installation_fit 신설 |
| 29 | inquiry_type_raw | Inquiry | 메타 | LLM 원 출력 보존(정규화 이전). 집계 사용 금지 · 택소노미 확장 후보 탐지용 | 자유 문자열 (예: installation_environment_fit) |
| 30 | need_signal_flag | Need | 최종값 | 니즈 여부 | Y / N |
| 31 | need_signal_type | Need | 최종값 | 니즈 유형(정규 enum). 원 출력은 need_signal_type_raw에 보존 | (값 목록 시트 참조) |
| 32 | need_signal_type_raw | Need | 메타 | LLM 원 출력 보존(정규화 이전). 집계 사용 금지 · 택소노미 확장 후보 탐지용 | 자유 문자열 (예: design) |
| 33 | entity_role | Entity | 최종값 | 주체 구분(자사/경쟁/채널/불명). 개선 우선순위 집계 라우팅 축(규율 v3 §17) | product_brand / competitor_brand / creator_channel / unknown |
| 34 | tee_time_score | TEE/S(Scoring) | 점수 | ★시간 비용 | -5 ~ +5 (0=언급 없음) |
| 35 | tee_time_evidence | TEE/S | 근거 | 시간 관련 발췌·차수 | 텍스트 |
| 36 | tee_effort_score | TEE/S(Scoring) | 점수 | ★노력 비용 | -5 ~ +5 (0=언급 없음) |
| 37 | tee_effort_evidence | TEE/S | 근거 | 노력 관련 발췌·차수 | 텍스트 |
| 38 | tee_emotion_score | TEE/S(Scoring) | 점수 | ★감정 영향 | -5 ~ +5 (0=언급 없음) |
| 39 | tee_emotion_evidence | TEE/S | 근거 | 감정 관련 발췌·차수 | 텍스트 |
| 40 | tee_success_score | TEE/S(Scoring) | 점수 | ★성과 영향 | -5 ~ +5 (0=언급 없음) |
| 41 | tee_success_evidence | TEE/S | 근거 | 성과 관련 발췌·차수 | 텍스트 |
| 42 | tee_summary | TEE/S | 중간값 | TEE/S 종합 서술 | 텍스트 |
| 43 | rootcause_problem | RootCause | 최종값 | 문제 현상. 3-게이트(R14) 통과 시에만 산출 | 텍스트 또는 N/A |
| 44 | rootcause_target | RootCause | 최종값 | 개선 대상 | 텍스트 |
| 45 | rootcause_cause | RootCause | 최종값 | 근본 원인 | 텍스트 |
| 46 | rootcause_summary | RootCause | 최종값 | 종합 서술 | 텍스트 |
| 47 | rootcause_score | RootCause(Scoring) | 점수 | ★개선 가능성(maturity). 3-게이트 통과 시에만 1 이상 | 0·1·3·5 (0=N/A · 1=L1문제 · 3=L2대상 · 5=L3원인) |
| 48 | confidence_rating | Scoring | 최종값 | ★분석 신뢰성(정보 충족도). 엔진 후처리 계산값 — LLM 출력 사용 금지. 정확도 지표 아님 | Low(Topic 없음) / Medium(Topic) / High(+TEE) / Very High(+RootCause) |
| 49 | voc_total_score | Scoring | 점수 | (선택) 축 합산 점수 | 정수(각 축 독립·합산 가능) |
| 50 | confidence_topic | 신뢰도(단계) | 신뢰도 | Topic 판단 신뢰도 | High / Medium / Low  (3단계 — Very High 유입 시 High로 절삭) |
| 51 | confidence_cej | 신뢰도(단계) | 신뢰도 | CEJ 판단 신뢰도 | High / Medium / Low  (3단계 — Very High 유입 시 High로 절삭) |
| 52 | confidence_inquiry | 신뢰도(단계) | 신뢰도 | Inquiry 판단 신뢰도 | High / Medium / Low  (3단계 — Very High 유입 시 High로 절삭) |
| 53 | confidence_need_signal | 신뢰도(단계) | 신뢰도 | Need 판단 신뢰도 | High / Medium / Low  (3단계 — Very High 유입 시 High로 절삭) |
| 54 | confidence_entity_role | 신뢰도(단계) | 신뢰도 | Entity role 판단 신뢰도 | High / Medium / Low  (3단계 — Very High 유입 시 High로 절삭) |
| 55 | confidence_score | 신뢰도(단계) | 신뢰도 | Score 단계 신뢰도 (A안: rating) | High / Medium / Low  (3단계 — Very High 유입 시 High로 절삭) |
| 56 | source_context_summary | 트레이스 | 중간값 | 판단 근거로 실제 주입된 컨텍스트 요약. reply면 parent_voc 포함 필수. 실행 파라미터는 포함 금지 | video_title / video_tags / parent_voc … |
| 57 | trace_summary | 트레이스 | 중간값 | 판단 경로 종합. 가드·오버라이드 발동 시 사유를 반드시 기록 | 텍스트 |
| 58 | status | 상태 | 메타 | 처리 상태. scope_excluded면 scope_exclusion_reason 필수 | normal / review_required / scope_excluded |
| 59 | review_required | 상태 | 메타 | 검토 필요 | Y / N |
| 60 | scope_exclusion_reason | 상태 | 메타 | status=scope_excluded 인 경우의 제외 사유. LLM이 제외 판정 시 반드시 함께 출력 | empty · operator_notice · channel_request · channel_feedback · out_of_scope_product · no_analytic_value · unresolvable_reply |
| 61 | proposal_flag | QA | 메타 | 값 출처(엔진/Cowork 제안) | engine_llm / engine_pre_llm_exclusion / cowork_proposal |
| 62 | video_id | 영상 | 중간값 | 영상 ID | (ID) |
| 63 | video_title | 영상 | 중간값 | 영상 제목 | 텍스트 |
| 64 | video_url | 영상 | 중간값 | 영상 URL | URL |
| 65 | product_category | 제품군 | 최종값 | 제품군(원문 우선 판단: 모델명+로청 기능어 → ①원문 ②parent ③영상) | 로봇청소기·식기세척기·세탁기·건조기·냉장고·기타 |
| 66 | product_category_source | 제품군 | 메타 | product_category 판단 근거 출처. 실행 힌트(keyword/product) 기반 확정 금지(v9 §2.7) | text · parent · video |

총 66개 컬럼

---

# 2. Enum 허용값

| 컬럼·구분 | 허용 값 | 비고 |
|---|---|---|
| cej (9단계) | 인지 · 탐색 · 결정 · 구매 · 배송 · 사용준비 · 사용 · 관리 · 교체 | 기본 9단계. "설치"는 허용값 아님 → 사용준비로 매핑(R15) |
| cej — 해당없음 | 해당없음 | 9단계 밖 catch-all |
| entity_role | product_brand · competitor_brand · creator_channel · unknown | 자사/경쟁사 라우팅 축 |
| inquiry_flag / need_signal_flag / review_required | Y · N | 질문형이면 inquiry_flag=Y 필수 |
| inquiry_type | none · feature_spec · product_comparison · product_identification · usage_environment_fit · installation_fit · promotion_benefit · as_trust_quality · review_request · purchase_path_link · other_question | installation_fit 신설(v2.7). 원 출력은 inquiry_type_raw 보존 |
| need_signal_type | none · feature_need · price_value_need · purchase_confidence_need · conversion_signal · problem_solution_need · trust_safety_need · content_information_need · environment_fit_need · purchase_path_need · positive_message_candidate · low_value | 엔진 허용값(확장 가능) |
| topic_score | 0 · 1 · 3 · 5 | 인사이트 가치 (Scoring 기준 시트) |
| tee_*_score | -5 · -3 · -1 · 0 · +1 · +3 · +5 | 시간·노력·감정·성과 각 축 |
| rootcause_score | 0 · 1 · 3 · 5 | 개선 가능성(maturity) |
| confidence_rating | Low · Medium · High · Very High | 4단계. 엔진 후처리 계산값(Topic 없음=Low / Topic=Medium / +TEE=High / +RootCause=Very High). 정보 충족도이며 정확도 아님 |
| confidence_topic/cej/inquiry/need_signal/entity_role/score | High · Medium · Low | 3단계. Very High 유입 시 High로 절삭 |
| status | normal · review_required · scope_excluded | scope_excluded면 scope_exclusion_reason 필수 |
| proposal_flag | engine_llm · engine_pre_llm_exclusion · cowork_proposal | Cowork 직접분석은 cowork_proposal |
| reference_brand | LG | 자사 기준(관점 정규화) |
| topic 특수값 | 미분류 · N/A | 미분류=실질 VoC지만 캐노니컬 라벨 없음 / N/A=실질 분석대상 아님. 빈칸 금지 |
| product_category | 로봇청소기 · 식기세척기 · 세탁기 · 건조기 · 냉장고 · 기타 | 신설(v2.5) · 원문 우선 판단 |
| topic 원칙(v3.0) | 이유 라벨만(제품·감성 분리). 구매의사/이탈 · 기타(로봇청소기/식기세척기/세탁기/냉장고) 포함 | topic은 LLM_JUDGED. 엔진 정규화·E1 근거 가드 적용 |
| product_category_source | text · parent · video | 실행 힌트(keyword/product) 기반 확정 금지 — 힌트로 정한 값을 text로 기록하면 오류(v9 §2.7) |
| scope_exclusion_reason | empty · operator_notice · channel_request · channel_feedback · out_of_scope_product · no_analytic_value · unresolvable_reply | 신설(v2.7) · LLM 제외 판정의 허용 사유 화이트리스트 |
| inquiry_type_raw / need_signal_type_raw | (자유 문자열) | 신설(v2.7) · LLM 원 출력 보존. 집계 사용 금지 |
| topic_provisional | (자유 문자열) | R-C3-16 · atomic 내용·조건·근거의 자유 서술. Enum 검증·집계·필터 사용 금지 |
| product | (출력 제외) | legacy 강등(v2.7) · product_category로 대체 |

---

# 3. Scoring 기준

| 축 | 점수 | 조건 | 예시 |
|---|---|---|---|
| Topic (0~5) | 0 | Topic=N/A | 의미 없는 단답 |
|  | 1 | Topic 존재 | ‘좋네요’ |
|  | 3 | 고객 니즈/문의 식별 가능 | ‘고양이 털도 흡입되나요?’ |
|  | 5 | 상품기획 인사이트 / 반복 기능 요구 | ‘반려동물 털 제거 기능 필요’ |
| TEE-Time (-5~+5) | -5 | 시간 소모로 사용/구매 포기 | 설정이 너무 오래 걸려 반품 |
|  | -3 | 예상보다 많은 시간 소요 | 연결하는데 너무 오래 걸림 |
|  | -1 | 다소 시간 소요 | 설정이 생각보다 오래 걸림 |
|  | 0 | 시간 관련 언급 없음 | 일반 문의 |
|  | +1 | 약간 시간 절약 | 조금 편해짐 |
|  | +3 | 명확한 시간 절약 | 청소시간 절반 감소 |
|  | +5 | 매우 큰 시간 절감 | 매일 1시간 청소 안 함 |
| TEE-Effort (-5~+5) | -5 | 과도한 노력으로 사용 포기 | 설정이 너무 복잡해 안 씀 |
|  | -3 | 상당한 노력 필요 | 계속 수동 조정 필요 |
|  | -1 | 다소 번거로움 | 조금 귀찮음 |
|  | 0 | 노력 관련 언급 없음 | 일반 후기 |
|  | +1 | 약간 편리함 | 생각보다 편함 |
|  | +3 | 명확한 노력 감소 | 손청소 거의 불필요 |
|  | +5 | 노력 자체 제거 | 신경 쓸 필요 없음 |
| TEE-Emotion (-5~+5) | -5 | 매우 강한 부정 감정 | 다신 안 살 겁니다 |
|  | -3 | 명확한 불만 | 정말 실망스럽네요 |
|  | -1 | 약한 불만 | 조금 아쉽습니다 |
|  | 0 | 감정 표현 없음 | 기능 문의 |
|  | +1 | 약한 긍정 | 괜찮네요 |
|  | +3 | 만족 | 매우 만족합니다 |
|  | +5 | 강한 긍정 | 주변에 추천하고 있음 |
| TEE-Success (-5~+5) | -5 | 목적 달성 실패 | 전혀 청소가 안 됨 |
|  | -3 | 기대 이하 성과 | 생각보다 별로 |
|  | -1 | 일부 성공 | 아쉽지만 사용 가능 |
|  | 0 | 성과 언급 없음 | 정보 문의 |
|  | +1 | 기대 충족 | 원하던 수준 |
|  | +3 | 기대 초과 | 생각보다 훨씬 좋음 |
|  | +5 | 매우 큰 성과 | 삶의 질이 달라짐 |
| Root Cause (0~5) | 0 | N/A — 문제 X (분석 제외/참고) |  |
|  | 1 | L1 — 문제만(대상 X) |  |
|  | 3 | L2 — 문제+개선대상(원인 X) |  |
|  | 5 | L3 — 문제+개선대상+원인 |  |
| Confidence (후처리 계산 · v2.7) | Low | Topic 없음 | 엔진이 계산해 강제. LLM 출력 사용 금지. 정보 충족도이며 정확도 아님 |
|  | Medium | Topic 존재 |  |
|  | High | Topic + TEE 존재 |  |
|  | Very High | Topic + TEE + Root Cause 완성 |  |


---

# 사이드카 컬럼 5종 — 66컬럼 계약 밖 【v4.6 신설】

`voc_secondary_dataset.csv` 는 **71컬럼**이다. 66컬럼 계약 + 사이드카 5종이다.
사이드카는 계약에 들어가지 않으므로 `validate_contract` 가 검사하지 않는다.
그러나 **분모 계산의 정본이 이 안에 있다.** 정의 없이 쓰면 안 된다.

| 컬럼 | 값 | 뜻 | 실측 분포 (1,570행) |
|---|---|---|---|
| `na_class` | `legitimate_na` · `not_legitimate_na` | topic 이 N/A 인 이유가 정당한가 | 정당 350 · 부당 1,220 |
| `qc_status_summary` | `PASS` · `SUGGESTED` · `FLAG` · (빈칸) | P-1 과잉라벨 점검 결과 | 빈칸 1,491 · PASS 37 · SUGGESTED 37 · FLAG 3 |
| `qc_rule_ids` | `QC-OVERLABEL-01` · (빈칸) | 발동한 QC 규칙 | 빈칸 1,491 · 79행 발동 |
| `split_origin_atomic_id` | atomic_id · (빈칸) | 2차에서 분리된 행의 원본 | 전량 빈칸 (분리 미반영 상태) |
| `secondary_topic_source` | `first_pass` · `secondary_read` | topic 값의 출처 | 전량 `first_pass` |

**`na_class` 주의** — 정본 §8.4-1 이 분모 계산에 쓰는 컬럼이다.

```
분모 = status=normal 이고, (na_class=="legitimate_na" 이면서 topic=="N/A") 인 행만 제외
```

`legitimate_na` 350행 중 실제로 `topic=="N/A"` 인 것은 275행뿐이다.
나머지 75행은 캐노니컬 라벨이 붙어 있어 분모에 남는다.
`na_class` 만 보고 빼면 분모가 1,186 이 되어 정본 1,261 과 어긋난다.

**`secondary_topic_source`** — 2차 판독이 topic 을 바꾸면 `secondary_read` 로 바뀐다.
`build_bundle.py` 가 `--apply` 시 기록한다. 어느 값이 사람 손을 거쳤는지 추적하는 축이다.

> 2026-08-14 CP-18 — 도구형 판독자(Claude Code)가 "산출 CSV 컬럼이
> 데이터사전 정의 수보다 많고, 그중 `na_class` 는 §8.4-1 이 분모 정본으로
> 지정한 컬럼인데 정의가 어디에도 없다" 고 지적해 신설했다.
> 판독자가 문서의 빈 곳을 찾아낸 첫 사례다.
