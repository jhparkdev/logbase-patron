// 기존 MOCK seed의 입력 스냅샷. 이미지 원본은 포함하지 않아 접근 불가로 표시한다.
export const historyInputSnapshots = {
  "01a0f5d5-6c80-73a6-a557-f5e687725c66": {
    scenarioKey: "2",
    mode: "scenario",
    prompt:
      "다음 상품 정보로 상세 설명 3문단과 마케팅 문구 1줄을 작성하세요.\n{{product_info}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.7",
    maxTokens: "1024",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: null,
    attachments: [],
  },
  "01a0ff7d-5900-73aa-8f25-2a74e5333265": {
    scenarioKey: "4",
    mode: "scenario",
    prompt: "다음 텍스트를 지정한 JSON Schema에 맞춰 변환하세요.\n{{text}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema:
      '{\n  "type": "object",\n  "required": [\n    "name",\n    "price",\n    "options"\n  ],\n  "properties": {\n    "name": {\n      "type": "string"\n    },\n    "price": {\n      "type": "integer"\n    },\n    "options": {\n      "type": "array",\n      "items": {\n        "type": "string"\n      }\n    }\n  }\n}',
    temperature: "0",
    maxTokens: "512",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: null,
    attachments: [],
  },
  "01a10ebe-1260-73ae-905d-01c7a6ea4fba": {
    scenarioKey: "1",
    mode: "scenario",
    prompt:
      "다음 상품 이미지를 보고 색상, 소재, 카테고리를 JSON으로 추출하세요.\n상품명: {{product_name}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema:
      '{\n  "type": "object",\n  "required": [\n    "color",\n    "material",\n    "category"\n  ],\n  "properties": {\n    "color": {\n      "type": "string"\n    },\n    "material": {\n      "type": "string"\n    },\n    "category": {\n      "type": "string"\n    }\n  }\n}',
    temperature: "0.2",
    maxTokens: "512",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: null,
    attachments: [
      {
        key: "01a10eb9-7e80-73a4-9602-19ecb73f3928",
        name: "sample-dress-01.jpg",
        available: false,
      },
      {
        key: "01a10eb9-8268-73a5-892a-6b3f431d074a",
        name: "sample-dress-02.jpg",
        available: false,
      },
    ],
  },
  "01a11a34-5640-73b1-8926-9cec7ce41e6f": {
    scenarioKey: "3",
    mode: "scenario",
    prompt: "다음 데이터를 5줄 이내로 요약하세요.\n{{data}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.3",
    maxTokens: "512",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "PARTIAL_SUCCESS",
    rerunOf: null,
    attachments: [],
  },
  "01a1249c-8580-73b6-b070-7fd607af2bdb": {
    scenarioKey: "",
    mode: "custom",
    prompt: "이 상품의 경쟁사 대비 강점을 3가지로 정리하세요. (Custom Prompt)",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.7",
    maxTokens: "",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "FAILED",
    rerunOf: null,
    attachments: [],
  },
  "01a12dd6-9500-73b9-b03a-f3d6b88f9caa": {
    scenarioKey: "4",
    mode: "scenario",
    prompt: "다음 텍스트를 지정한 JSON Schema에 맞춰 변환하세요.\n{{text}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema:
      '{\n  "type": "object",\n  "required": [\n    "name",\n    "price",\n    "options"\n  ],\n  "properties": {\n    "name": {\n      "type": "string"\n    },\n    "price": {\n      "type": "integer"\n    },\n    "options": {\n      "type": "array",\n      "items": {\n        "type": "string"\n      }\n    }\n  }\n}',
    temperature: "0",
    maxTokens: "512",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: "01a0ff7d-5900-73aa-8f25-2a74e5333265",
    attachments: [],
  },
  "01a13dee-7480-73bd-b16e-53442b2016c5": {
    scenarioKey: "5",
    mode: "scenario",
    prompt: "다음 판매 데이터를 보고 다음 달 재고 전략을 제안하세요.\n{{data}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.5",
    maxTokens: "1024",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: null,
    attachments: [],
  },
  "01a14d2a-9a00-73c1-a64d-bcd0ebca3bdf": {
    scenarioKey: "2",
    mode: "scenario",
    prompt:
      "다음 상품 정보로 상세 설명 3문단과 마케팅 문구 1줄을 작성하세요.\n{{product_info}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.7",
    maxTokens: "1024",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: null,
    attachments: [],
  },
  "01a1611f-3e80-73c5-a130-3efa5a1f75de": {
    scenarioKey: "3",
    mode: "scenario",
    prompt: "다음 데이터를 5줄 이내로 요약하세요.\n{{data}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.3",
    maxTokens: "512",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: "01a11a34-5640-73b1-8926-9cec7ce41e6f",
    attachments: [],
  },
  "01a16721-5480-73c9-9f6a-825bd5291f61": {
    scenarioKey: "3",
    mode: "scenario",
    prompt: "다음 데이터를 5줄 이내로 요약하세요.\n{{data}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.3",
    maxTokens: "512",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "SUCCESS",
    rerunOf: null,
    attachments: [],
  },
  "01a16cec-7c00-73cd-82b5-203c36eb3b83": {
    scenarioKey: "2",
    mode: "scenario",
    prompt:
      "다음 상품 정보로 상세 설명 3문단과 마케팅 문구 1줄을 작성하세요.\n{{product_info}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.7",
    maxTokens: "1024",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "CANCELLED",
    rerunOf: null,
    attachments: [],
  },
  "01a1705b-6400-73d0-af56-c508b2430f9a": {
    scenarioKey: "3",
    mode: "scenario",
    prompt: "다음 데이터를 5줄 이내로 요약하세요.\n{{data}}",
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    jsonSchema: "",
    temperature: "0.3",
    maxTokens: "512",
    routingPolicy:
      '{\n  "allow_fallbacks": false,\n  "require_parameters": true\n}',
    status: "RUNNING",
    rerunOf: null,
    attachments: [],
  },
} as const;
