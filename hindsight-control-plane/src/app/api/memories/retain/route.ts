import { NextRequest, NextResponse } from "next/server";
import { localizeApiErrorPayload } from "@/lib/i18n/api-errors";
import { sdk, lowLevelClient } from "@/lib/hindsight-client";
import { respondWithSdk } from "@/lib/sdk-response";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const bankId = body.bank_id || body.agent_id;

    if (!bankId) {
      return NextResponse.json(
        localizeApiErrorPayload(request, {
          error: "bank_id is required",
          errorKey: "api.errors.validation.bankIdRequired",
        }),
        { status: 400 }
      );
    }

    const { items, document_id, document_tags, observation_scopes } = body;

    // Apply request-level defaults to each item and ensure batch-level
    // document_id propagates to items without their own. tag_enumerations,
    // when present on an item, is forwarded verbatim; the dataplane validates
    // its shape.
    const mappedItems = Array.isArray(items)
      ? items.map((item: any) => ({
          ...item,
          observation_scopes: item.observation_scopes ?? observation_scopes,
          document_id: item.document_id ?? document_id,
        }))
      : items;

    const response = await sdk.retainMemories({
      client: lowLevelClient,
      path: { bank_id: bankId },
      body: { items: mappedItems, document_tags },
    });

    return respondWithSdk(response, "Failed to batch retain", { request });
  } catch (error: any) {
    console.error("Error batch retain:", error);

    const errorMessage = error?.message || String(error);
    const errorDetails = error?.details;
    const statusCode = error?.statusCode;

    // If we have a statusCode, use it
    if (statusCode && typeof statusCode === "number") {
      return NextResponse.json(
        localizeApiErrorPayload(request, {
          error: errorMessage,
          details: errorDetails,
          errorKey: "api.errors.memories.retain",
        }),
        { status: statusCode }
      );
    }

    // Otherwise, return generic 500 error
    return NextResponse.json(
      localizeApiErrorPayload(request, {
        error: errorMessage || "Failed to batch retain",
        errorKey: "api.errors.memories.retain",
      }),
      { status: 500 }
    );
  }
}
