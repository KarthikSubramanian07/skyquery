// Public, read-only metadata API. See /openapi.json for the contract.
import { handleApi } from "../../edge/agent.js";

export const onRequest = ({ request, env }) => handleApi(request, env);
