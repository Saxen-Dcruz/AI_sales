"""
RAGAS evaluation for RDL AI Sales RAG pipeline.
Metrics: Faithfulness, ResponseRelevancy, LLMContextPrecisionWithReference, LLMContextRecall
LangSmith tracing: auto-enabled when LANGCHAIN_API_KEY is set in env.

Run inside container:
    docker compose exec backend bash -c "cd /app && PYTHONPATH=/app python test_rag_eval.py"
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── RAGAS imports ────────────────────────────────────────────────────────────
from ragas import evaluate
from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
from ragas.metrics import (  # old path — LangchainLLMWrapper compatible in 0.4.x
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# ── LangChain / Google ───────────────────────────────────────────────────────
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ── Project ──────────────────────────────────────────────────────────────────
from app.core.config import settings
from app.agents.tools.rag_chain import RAGManager

# ─────────────────────────────────────────────────────────────────────────────
# TEST DATASET
# Ground truths are minimal correct-answer statements — enough for RAGAS
# context_recall to measure whether context contains the key facts.
# ─────────────────────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": "Q01_price_biometric",
        "session_id": "00000000-0000-0000-0000-000000000001",
        "tier": "factual",
        "question": "What is the price of the Biometric Authentication System for PLC and SCADA?",
        "ground_truth": (
            "The price for Biometric Authentication System for PLC and SCADA is ₹13,500."
        ),
    },
    {
        "id": "Q02_features_soil_sensor",
        "session_id": "00000000-0000-0000-0000-000000000002",
        "tier": "standard",
        "question": "What are the features of the Digital Soil Moisture Sensor?",
        "ground_truth": (
            "The Digital Soil Moisture Sensor provides digital output for soil moisture measurement. "
            "It can detect moisture levels in soil and is used in agriculture and irrigation automation."
        ),
    },
    {
        "id": "Q03_compare_arm_boards",
        "session_id": "00000000-0000-0000-0000-000000000003",
        "tier": "expanded",
        "question": "Compare the ARM Development Board LPC2129 and ARM Development Board LPC2148",
        "ground_truth": (
            "The ARM Development Board LPC2129 is priced at ₹8,231 and uses the LPC2129 microcontroller. "
            "The ARM Development Board LPC2148 is priced at ₹7,999 and uses the LPC2148 microcontroller. "
            "Both are 32-bit ARM7TDMI-S based development boards."
        ),
    },
    {
        "id": "Q04_applications_data_logger",
        "session_id": "00000000-0000-0000-0000-000000000004",
        "tier": "standard",
        "question": "What are the applications of the Industrial Data Logger 4G LTE?",
        "ground_truth": (
            "The Industrial Data Logger 4G LTE is used for remote monitoring and data logging "
            "of industrial sensors and equipment. Applications include energy monitoring, "
            "factory automation, and IoT data acquisition over 4G LTE networks."
        ),
    },
    {
        "id": "Q05_iot_kit_contents",
        "session_id": "00000000-0000-0000-0000-000000000005",
        "tier": "expanded",
        "question": "What is included in the IoT Starter Kit Energy Monitoring Kit?",
        "ground_truth": (
            "The IoT Starter Kit Energy Monitoring Kit includes: "
            "Data Logger RDL838, Energy Meter (3 phase, Modbus RS485), and CT Coil (50A)."
        ),
    },
    {
        "id": "Q06_cloud_plc_4g_specs",
        "session_id": "00000000-0000-0000-0000-000000000006",
        "tier": "standard",
        "question": "What are the specifications of the Cloud PLC 4G/LTE?",
        "ground_truth": (
            "The Cloud PLC 4G/LTE supports 4G LTE communication for remote PLC operations. "
            "It is priced at ₹7,499 and is used for industrial automation and remote monitoring."
        ),
    },
    {
        "id": "Q07_price_digital_temp_sensor",
        "session_id": "00000000-0000-0000-0000-000000000007",
        "tier": "factual",
        "question": "How much does the Digital Temperature Sensor cost?",
        "ground_truth": "The Digital Temperature Sensor is priced at ₹249.",
    },
    {
        "id": "Q08_what_is_pic_development_board",
        "session_id": "00000000-0000-0000-0000-000000000008",
        "tier": "standard",
        "question": "What is the PIC Development Board Trainer Kit?",
        "ground_truth": (
            "The PIC Development Board is a high-quality PIC microcontroller development board "
            "designed for Industrial Developers, Engineering students, Hobbyists, and DIY projects. "
            "It features a DIP40 locking ZIF socket for easy IC mounting and onboard peripherals "
            "for developing and testing PIC-based embedded systems."
        ),
    },
    {
        "id": "Q09_modbus_tcp_gateway",
        "session_id": "00000000-0000-0000-0000-000000000009",
        "tier": "standard",
        "question": "What is the Modbus TCP Gateway used for?",
        "ground_truth": (
            "The Modbus TCP Gateway is used to convert serial Modbus RTU/ASCII communication to "
            "Modbus TCP over Ethernet, enabling integration of legacy industrial devices into "
            "modern networked systems. It is priced at ₹4,499."
        ),
    },
    {
        "id": "Q10_current_sensor_30a",
        "session_id": "00000000-0000-0000-0000-000000000010",
        "tier": "factual",
        "question": "What is the price and specifications of the Hall Effect Current Sensor 30A?",
        "ground_truth": (
            "The Hall Effect Current Sensor 30A measures AC/DC current up to 30 amperes "
            "using the Hall effect principle. It is priced at ₹345."
        ),
    },
]


async def run_eval():
    print("=" * 60)
    print("RDL RAG Pipeline — RAGAS Evaluation")
    print(f"Model: {settings.AGENT.rag.llm_model}")
    print(f"Embedding: {settings.AGENT.rag.embedding_model}")
    print(f"Questions: {len(TEST_CASES)}")
    print("=" * 60)

    # ── Initialize RAG ───────────────────────────────────────────────────────
    rag = RAGManager()
    await rag.initialize_rag()

    # ── Run each question ────────────────────────────────────────────────────
    samples = []
    per_question_results = []

    for tc in TEST_CASES:
        print(f"\n[{tc['id']}] {tc['question'][:80]}...")
        t0 = time.perf_counter()
        result = await rag.query_rag_database(tc["question"], session_id=tc["session_id"])
        latency = int((time.perf_counter() - t0) * 1000)

        answer = result.get("answer", "")
        contexts = result.get("contexts", [])
        reranker_docs = result.get("reranker_doc_count", 0)
        token_tier = result.get("token_tier", "unknown")
        usage = result.get("usage", {})

        print(f"  tier={token_tier} | docs={reranker_docs} | latency={latency}ms")
        print(f"  in={usage.get('input_tokens',0)} out={usage.get('output_tokens',0)}")
        print(f"  answer: {answer[:120]}...")

        per_question_results.append({
            "id": tc["id"],
            "question": tc["question"],
            "answer": answer,
            "contexts": contexts,
            "ground_truth": tc["ground_truth"],
            "latency_ms": latency,
            "token_tier": token_tier,
            "reranker_doc_count": reranker_docs,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        })

        samples.append(
            SingleTurnSample(
                user_input=tc["question"],
                retrieved_contexts=contexts if contexts else [""],
                response=answer,
                reference=tc["ground_truth"],
            )
        )

    # ── Build RAGAS dataset ──────────────────────────────────────────────────
    eval_dataset = EvaluationDataset(samples=samples)

    # ── Configure RAGAS LLM + Embeddings ────────────────────────────────────
    ragas_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=settings.AGENT.rag.llm_model,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
        )
    )
    ragas_embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(
            model=settings.AGENT.rag.embedding_model,
            google_api_key=settings.GOOGLE_API_KEY,
        )
    )

    metrics = [
        Faithfulness(),
        AnswerRelevancy(),
        ContextPrecision(),
        ContextRecall(),
    ]

    print("\n" + "=" * 60)
    print("Running RAGAS evaluation...")
    print("=" * 60)

    ragas_result = evaluate(
        dataset=eval_dataset,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=ragas_embeddings,
    )

    # ── Print results ────────────────────────────────────────────────────────
    df = ragas_result.to_pandas()

    print("\n=== RAGAS SCORES ===")
    score_cols = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    available_cols = [c for c in score_cols if c in df.columns]

    for i, row in df.iterrows():
        qr = per_question_results[i]
        print(f"\n{qr['id']} | tier={qr['token_tier']} | docs={qr['reranker_doc_count']} | {qr['latency_ms']}ms")
        for col in available_cols:
            val = row.get(col, None)
            score_str = f"{val:.3f}" if val is not None and val == val else "N/A"
            print(f"  {col}: {score_str}")

    print("\n=== AGGREGATE SCORES ===")
    agg = {}
    for col in available_cols:
        vals = [v for v in df[col] if v == v]  # filter NaN
        if vals:
            agg[col] = sum(vals) / len(vals)
            print(f"  {col}: {agg[col]:.3f}")

    # ── Identify problem areas ───────────────────────────────────────────────
    print("\n=== PROBLEM ANALYSIS ===")
    FAIL_THRESHOLD = 0.6

    for i, row in df.iterrows():
        qr = per_question_results[i]
        fails = []
        for col in available_cols:
            val = row.get(col, None)
            if val is not None and val == val and val < FAIL_THRESHOLD:
                fails.append(f"{col}={val:.3f}")
        if fails:
            print(f"  FAIL [{qr['id']}]: {', '.join(fails)}")
            print(f"    Q: {qr['question'][:80]}")
            print(f"    A: {qr['answer'][:120]}")

    if all(
        (row.get(col, 1.0) or 1.0) >= FAIL_THRESHOLD
        for _, row in df.iterrows()
        for col in available_cols
    ):
        print("  All questions passed (>= 0.6 on all metrics)")

    # ── Persist to rag_metrics.md ────────────────────────────────────────────
    _write_metrics_log(per_question_results, agg, available_cols)

    return agg


def _write_metrics_log(results, agg, score_cols):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Write to /tmp inside container — caller reads it and appends to host .claude/rag_metrics.md
    metrics_path = Path("/tmp/rag_metrics_entry.md")

    rows = []
    for r in results:
        rows.append(f"| {r['id']} | {r['token_tier']} | {r['reranker_doc_count']} | {r['latency_ms']}ms |")

    agg_str = " | ".join(f"{k.split('_')[0][:8]}={v:.3f}" for k, v in agg.items())
    avg_latency = sum(r["latency_ms"] for r in results) // len(results)
    total_input = sum(r["input_tokens"] for r in results)
    total_output = sum(r["output_tokens"] for r in results)

    entry = f"""
## {now} — RAGAS eval: {len(results)} questions (Saxen)

### Config
- LLM: {settings.AGENT.rag.llm_model}
- Embedding: {settings.AGENT.rag.embedding_model}
- Reranker: ms-marco-MultiBERT-L-12 | top_n=5 | threshold=0.3
- Retrieval k: 8

### Aggregate Scores
| Metric | Score |
|---|---|
""" + "\n".join(
        f"| {col} | {agg.get(col, 'N/A'):.3f} |" for col in score_cols if col in agg
    ) + f"""

### Per-Question Summary
| ID | Tier | Docs | Latency |
|---|---|---|---|
""" + "\n".join(rows) + f"""

### Token Usage
- Total input tokens: {total_input}
- Total output tokens: {total_output}
- Avg latency: {avg_latency}ms

### Aggregate: {agg_str}

---
"""

    with open(metrics_path, "a") as f:
        f.write(entry)

    print(f"\nMetrics appended to .claude/rag_metrics.md")


if __name__ == "__main__":
    asyncio.run(run_eval())
