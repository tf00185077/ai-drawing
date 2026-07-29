import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import LoraTrain from "./LoraTrain";

type FetchCall = {
  url: string;
  init?: RequestInit;
};

const recipeHash = "a".repeat(64);

const exactStartPayload = {
  folder: "dataset-a",
  expected_dataset_hash: "dataset-hash-approved",
  expected_profile_hash: "profile-hash-approved",
  recipe: {
    schema_version: "lora-training-recipe/v1",
    expected_recipe_hash: recipeHash,
    model: {
      family: "anima",
      checkpoint: "anima-base.safetensors",
      anima: {
        qwen3: "qwen3.safetensors",
        vae: "anima-vae.safetensors",
      },
    },
    dataset: {
      trigger_token: "hero_token",
    },
    optimization: {
      seed: {
        mode: "random",
        value: 1700000001,
        source: "preflight_policy",
      },
    },
    caching: {
      cache_latents: true,
      cache_text_encoder_outputs: true,
      cache_to_disk: true,
    },
  },
};

const readyPreflight = {
  ok: true,
  folder: "dataset-a",
  decision: "train",
  reasons: ["Dataset is ready for training."],
  blocking_issues: [],
  warnings: [],
  next_actions: ["Start the approved training run."],
  dataset_hash: "dataset-hash-approved",
  profile_hash: "profile-hash-approved",
  normalized_trigger_token: "hero_token",
  requested_recipe: {
    ...exactStartPayload.recipe,
    expected_recipe_hash: null,
  },
  effective_recipe: {
    schema_version: "lora-training-recipe/v1",
    model: {
      family: "anima",
      checkpoint: "D:/models/anima-base.safetensors",
      allow_unverified_checkpoint: false,
      network_module: "networks.lora_anima",
      network_dim: 32,
      network_alpha: 16,
      anima: {
        qwen3: "D:/models/qwen3.safetensors",
        vae: "D:/models/anima-vae.safetensors",
        t5_tokenizer_path: null,
      },
    },
    scope: {
      denoiser_kind: "dit",
      train_denoiser: true,
      train_text_encoder: false,
      native_scope_flag: "--network_train_unet_only",
      verification_status: "source_contract",
    },
    dataset: {
      trigger_token: "hero_token",
      class_tokens: "hero_token",
      resolution: 1024,
      batch_size: 1,
      keep_tokens: 1,
      num_repeats: 8,
      enable_bucket: true,
      bucket_no_upscale: true,
      min_bucket_reso: 256,
      max_bucket_reso: 2048,
      bucket_reso_steps: 64,
    },
    optimization: {
      epochs: 8,
      learning_rate: "0.0001",
      denoiser_learning_rate: "0.0001",
      text_encoder_learning_rates: [],
      gradient_accumulation_steps: 1,
      optimizer_type: "AdamW",
      optimizer_args: [],
      lr_scheduler: "constant",
      lr_scheduler_args: [],
      warmup: { mode: "steps", value: 0, resolved_steps: 0 },
      seed: exactStartPayload.recipe.optimization.seed,
      mixed_precision: "no",
    },
    caching: {
      cache_latents: true,
      cache_text_encoder_outputs: true,
      cache_to_disk: true,
      latent_cache_to_disk: true,
      text_encoder_cache_to_disk: true,
    },
    execution: {
      max_data_loader_n_workers: 0,
      persistent_data_loader_workers: false,
      save_every_n_epochs: 1,
      final_only: false,
    },
    server: {
      gradient_checkpointing: true,
      caption_extension: ".txt",
      shuffle_caption: true,
      save_model_as: "safetensors",
      launcher_num_cpu_threads_per_process: 2,
    },
  },
  requested_scope: null,
  effective_scope: {
    denoiser_kind: "dit",
    train_denoiser: true,
    train_text_encoder: false,
    native_scope_flag: "--network_train_unet_only",
    verification_status: "source_contract",
  },
  field_sources: {
    "model.family": "caller",
    "dataset.batch_size": "preflight_policy",
    "optimization.seed": "preflight_policy",
  },
  step_plan: {
    image_count: 12,
    num_repeats: 8,
    train_examples: 96,
    batch_size: 1,
    batches_per_epoch: 96,
    gradient_accumulation_steps: 1,
    optimizer_steps_per_epoch: 96,
    epochs: 8,
    total_optimizer_steps: 768,
    warmup_steps: 0,
    process_count: 1,
  },
  component_identities: {
    checkpoint: {
      kind: "checkpoint",
      requested_locator: "anima-base.safetensors",
      resolved_locator: "D:/models/anima-base.safetensors",
      size_bytes: 1024,
      modified_time_ns: 123,
      sha256: "b".repeat(64),
      verification_status: "verified",
      reason: null,
      bypass_used: false,
    },
  },
  capability: {
    platform: "unknown",
    status: "unavailable",
    reason: "trainer runtime inspection failed",
    torch_version: null,
    accelerate_version: null,
    python_version: null,
    supported_mixed_precision: ["no"],
  },
  execution_evidence: null,
  recipe_hash: recipeHash,
  policy_rationale: ["Anima uses conservative batch and precision policy."],
  start_payload: exactStartPayload,
  suggested_params: {
    params: exactStartPayload,
    rationale: ["Compatibility projection of the exact Start payload."],
  },
};

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

function installFetch(
  preflightResponse: Response,
  startResponse = response({ job_id: "job-1", status: "queued" }, 202),
  configResponse = response({ sdxl: true, model_family: "sdxl" }),
) {
  const calls: FetchCall[] = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      calls.push({ url, init });

      if (url === "/api/lora-train/status") {
        return response({ status: "idle", queue: [], last_result: null });
      }
      if (url === "/api/lora-train/folders") {
        return response({
          folders: [{ folder: "dataset-a", image_count: 12 }],
        });
      }
      if (url === "/api/lora-train/config") {
        return configResponse;
      }
      if (url === "/api/lora-train/datasets/training-decision-preflight") {
        return preflightResponse;
      }
      if (url === "/api/lora-train/start") {
        return startResponse;
      }
      throw new Error(`Unexpected request: ${url}`);
    }),
  );

  return calls;
}

async function selectDatasetAndStart(batchSize?: string) {
  render(<LoraTrain />);
  fireEvent.click(
    await screen.findByRole("button", { name: /dataset-a/ }),
  );
  if (batchSize != null) {
    fireEvent.change(screen.getByPlaceholderText("4"), {
      target: { value: batchSize },
    });
  }
  fireEvent.click(screen.getByRole("button", { name: "開始訓練" }));
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("LoraTrain preflight start flow", () => {
  it("submits the exact preflight start_payload without reconstructing unseen defaults", async () => {
    const calls = installFetch(response(readyPreflight));

    await selectDatasetAndStart();

    await waitFor(() => {
      expect(
        calls
          .filter((call) => call.init?.method === "POST")
          .map((call) => call.url),
      ).toEqual([
        "/api/lora-train/datasets/training-decision-preflight",
        "/api/lora-train/start",
      ]);
    });

    const preflightCall = calls.find(
      (call) =>
        call.url ===
        "/api/lora-train/datasets/training-decision-preflight",
    );
    expect(JSON.parse(String(preflightCall?.init?.body))).toEqual({
      folder: "dataset-a",
    });

    const startCall = calls.find(
      (call) => call.url === "/api/lora-train/start",
    );
    expect(JSON.parse(String(startCall?.init?.body))).toEqual({
      folder: "dataset-a",
      expected_dataset_hash: "dataset-hash-approved",
      expected_profile_hash: "profile-hash-approved",
      recipe: {
        schema_version: "lora-training-recipe/v1",
        expected_recipe_hash: recipeHash,
        model: {
          family: "anima",
          checkpoint: "anima-base.safetensors",
          anima: {
            qwen3: "qwen3.safetensors",
            vae: "anima-vae.safetensors",
          },
        },
        dataset: {
          trigger_token: "hero_token",
        },
        optimization: {
          seed: {
            mode: "random",
            value: 1700000001,
            source: "preflight_policy",
          },
        },
        caching: {
          cache_latents: true,
          cache_text_encoder_outputs: true,
          cache_to_disk: true,
        },
      },
    });
  });

  it("sends a supported override through recipe preflight before starting its recompiled payload", async () => {
    const overrideHash = "c".repeat(64);
    const overrideStartPayload = {
      ...exactStartPayload,
      recipe: {
        ...exactStartPayload.recipe,
        expected_recipe_hash: overrideHash,
        dataset: {
          ...exactStartPayload.recipe.dataset,
          batch_size: 2,
        },
      },
    };
    const calls = installFetch(
      response({
        ...readyPreflight,
        recipe_hash: overrideHash,
        requested_recipe: {
          ...readyPreflight.requested_recipe,
          dataset: {
            ...readyPreflight.requested_recipe.dataset,
            batch_size: 2,
          },
        },
        start_payload: overrideStartPayload,
        suggested_params: {
          params: overrideStartPayload,
          rationale: ["The caller explicitly requested batch size 2."],
        },
      }),
    );

    await selectDatasetAndStart("2");

    await waitFor(() => {
      expect(
        calls.filter((call) => call.url === "/api/lora-train/start"),
      ).toHaveLength(1);
    });

    const preflightCall = calls.find(
      (call) =>
        call.url ===
        "/api/lora-train/datasets/training-decision-preflight",
    );
    expect(JSON.parse(String(preflightCall?.init?.body))).toEqual({
      folder: "dataset-a",
      recipe: {
        dataset: {
          batch_size: 2,
        },
      },
    });
    const startCall = calls.find(
      (call) => call.url === "/api/lora-train/start",
    );
    expect(JSON.parse(String(startCall?.init?.body))).toEqual(
      overrideStartPayload,
    );
  });

  it("does not call Start when preflight requires review and shows the next action", async () => {
    const calls = installFetch(
      response({
        ...readyPreflight,
        decision: "needs_review",
        reasons: ["Configured family conflicts with the dataset profile."],
        warnings: [
          {
            code: "model_family_mismatch",
            message: "The configured family is SDXL but the profile is SD1.5.",
            path: null,
            details: {},
          },
        ],
        next_actions: ["Select a checkpoint matching the dataset profile."],
        start_payload: null,
        suggested_params: null,
      }),
    );

    await selectDatasetAndStart();

    expect(
      await screen.findByText(
        /needs_review.*model_family_mismatch.*Select a checkpoint matching the dataset profile\./,
      ),
    ).toBeInTheDocument();
    expect(
      calls.some((call) => call.url === "/api/lora-train/start"),
    ).toBe(false);
  });

  it("does not call Start when preflight says do not train and shows the blocking issue", async () => {
    const calls = installFetch(
      response({
        ...readyPreflight,
        decision: "do_not_train",
        reasons: ["Captions are incomplete."],
        blocking_issues: [
          {
            code: "missing_caption",
            message: "One or more images have no caption.",
            path: "image-01.png",
            details: {},
          },
        ],
        next_actions: ["Add the missing captions and rerun preflight."],
        start_payload: null,
        suggested_params: null,
      }),
    );

    await selectDatasetAndStart();

    expect(
      await screen.findByText(
        /do_not_train.*missing_caption.*Add the missing captions and rerun preflight\./,
      ),
    ).toBeInTheDocument();
    expect(
      calls.some((call) => call.url === "/api/lora-train/start"),
    ).toBe(false);
  });

  it("does not call Start when preflight fails and shows the structured backend error", async () => {
    const calls = installFetch(
      response(
        {
          detail: {
            code: "invalid_dataset_folder",
            message: "Dataset folder resolves outside the training root.",
            details: {},
          },
        },
        400,
      ),
    );

    await selectDatasetAndStart();

    expect(
      await screen.findByText(
        /invalid_dataset_folder.*Dataset folder resolves outside the training root\./,
      ),
    ).toBeInTheDocument();
    expect(
      calls.some((call) => call.url === "/api/lora-train/start"),
    ).toBe(false);
  });

  it("shows stale-hash details and requires a new preflight when Start races with a dataset change", async () => {
    const calls = installFetch(
      response(readyPreflight),
      response(
        {
          detail: {
            code: "dataset_hash_mismatch",
            message: "Dataset changed after approval.",
            details: {
              expected_dataset_hash: "dataset-hash-approved",
              current_dataset_hash: "dataset-hash-current",
            },
          },
        },
        409,
      ),
    );

    await selectDatasetAndStart();

    expect(
      await screen.findByText(
        /dataset_hash_mismatch.*Dataset changed after approval.*current_dataset_hash=dataset-hash-current.*rerun preflight/i,
      ),
    ).toBeInTheDocument();
    expect(
      calls.filter((call) => call.url === "/api/lora-train/start"),
    ).toHaveLength(1);
  });

  it("shows field-level Start validation details without retrying with defaults", async () => {
    const calls = installFetch(
      response(readyPreflight),
      response(
        {
          detail: [
            {
              loc: ["body", "expected_profile_hash"],
              msg: "Field required",
              type: "missing",
            },
          ],
        },
        422,
      ),
    );

    await selectDatasetAndStart();

    expect(
      await screen.findByText(
        /body\.expected_profile_hash: Field required/,
      ),
    ).toBeInTheDocument();
    expect(
      calls.filter((call) => call.url === "/api/lora-train/start"),
    ).toHaveLength(1);
  });

  it("does not call Start when a train decision omits its exact start_payload", async () => {
    const calls = installFetch(
      response({
        ...readyPreflight,
        start_payload: null,
      }),
    );

    await selectDatasetAndStart();

    expect(
      await screen.findByText(
        /missing canonical start_payload.*rerun preflight/i,
      ),
    ).toBeInTheDocument();
    expect(
      calls.some((call) => call.url === "/api/lora-train/start"),
    ).toBe(false);
  });

  it("does not call Start when a train decision returns a malformed truthy start_payload", async () => {
    const calls = installFetch(
      response({
        ...readyPreflight,
        start_payload: {
          folder: "dataset-a",
          expected_dataset_hash: "dataset-hash-approved",
          expected_profile_hash: "profile-hash-approved",
          recipe: {
            schema_version: "lora-training-recipe/v1",
            expected_recipe_hash: recipeHash,
          },
        },
      }),
    );

    await selectDatasetAndStart();

    expect(
      await screen.findByText(
        /invalid canonical start_payload.*rerun preflight/i,
      ),
    ).toBeInTheDocument();
    expect(
      calls.some((call) => call.url === "/api/lora-train/start"),
    ).toBe(false);
  });
});
