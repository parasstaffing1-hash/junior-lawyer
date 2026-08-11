# Evidence examples

Batch 15 evidence endpoints are matter-security aware. Typical flow:

1. Process matter documents through the existing document engine.
2. `POST /api/v1/evidence/matters/{matter_id}/rebuild`.
3. Review classifications and mark evidence items reviewed.
4. Add/edit litigation issues and map supporting/contradicting evidence.
5. Resolve or dismiss evidence-gap review items only after lawyer review.
6. Create witness-preparation prompts and adapt them to the actual witness and record.
7. Create a hearing/trial bundle. Finalization is blocked until all bundled evidence items are lawyer-reviewed.

The system does not declare authenticity, admissibility, evidentiary weight, or credibility automatically.
