"""Diagnose CAM pipeline failure."""
import asyncio
import sys
import os
import logging

# Load .env
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

from cam.context_assembler import assemble_cam_context

async def main():
    job_id = "94bb1247-c9d3-4e1b-a6d4-9a3679b44309"
    print(f"\\n=== Testing CAM context assembly for {job_id} ===")
    try:
        ctx = await assemble_cam_context(job_id)
        print(f"Context OK: company={ctx.company_name}, sector={ctx.sector}")
        print(f"  final_score={ctx.final_score}, layer1={ctx.layer1_score}, layer2={ctx.layer2_score}")
    except Exception as e:
        print(f"Context FAILED: {e}")
        import traceback; traceback.print_exc()
        return

    print("\\n=== Testing Accountant Persona ===")
    try:
        from cam.persona_accountant import run_accountant_persona
        acc = await run_accountant_persona(ctx)
        print(f"Accountant OK: keys={list(acc.keys())}")
    except Exception as e:
        print(f"Accountant FAILED: {e}")
        import traceback; traceback.print_exc()
        return

    print("\\n=== Testing Compliance Persona ===")
    try:
        from cam.persona_compliance import run_compliance_persona
        comp = await run_compliance_persona(ctx)
        print(f"Compliance OK: keys={list(comp.keys())}")
    except Exception as e:
        print(f"Compliance FAILED: {e}")
        import traceback; traceback.print_exc()
        return

    print("\\n=== Testing CRO Persona ===")
    try:
        from cam.persona_cro import run_cro_persona
        cro = await run_cro_persona(ctx, acc, comp)
        print(f"CRO OK: keys={list(cro.keys())}")
    except Exception as e:
        print(f"CRO FAILED: {e}")
        import traceback; traceback.print_exc()
        return

    print("\\n=== ALL PERSONAS PASSED ===")

asyncio.run(main())
