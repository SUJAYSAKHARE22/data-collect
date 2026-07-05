import asyncio
from pathlib import Path
from app.agents.context_builder import build_project_context
from app.agents.code_analysis_agent import CodeAnalysisAgent
from app.agents.llm_provider import KimiProvider
from app.config.settings import get_settings
from app.storage.storage_manager import StorageManager

async def main():
    settings = get_settings()
    job_id = "8dd8f4cd1b004b9b900e40288ab3746d"
    source_storage = StorageManager(settings.output_dir, job_id)

    metadata = source_storage.read_json("metadata.json")
    tree = source_storage.read_json("tree.json")
    files = source_storage.read_json("files.json")

    ctx = build_project_context(
        metadata=metadata,
        tree=tree,
        files=files,
        project_dir=source_storage.project_dir,
        max_files=settings.analysis_max_files,
        max_file_chars=settings.analysis_max_file_chars,
        max_total_chars=settings.analysis_max_total_chars,
    )

    provider = KimiProvider(
        api_key=settings.kimi_api_key,
        base_url=settings.kimi_base_url,
        model=settings.kimi_model,
        timeout_seconds=settings.kimi_timeout_seconds,
        max_retries=settings.kimi_max_retries,
    )

    agent = CodeAnalysisAgent(
        provider,
        max_tokens=settings.kimi_max_tokens,
        temperature=settings.kimi_temperature,
    )

    print("Running code analysis agent on job:", job_id)
    try:
        report = await agent.run(ctx)
        print("Success! Report keys:", list(report.keys()))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
