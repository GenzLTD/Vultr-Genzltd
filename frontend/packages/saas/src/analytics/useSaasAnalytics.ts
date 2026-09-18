import { useEffect } from "react";
import { initAnalytics } from "@looma/shared-core";
import { createSaasApiClient } from "../api/saasApiClient";

export function useSaasAnalytics() {
  useEffect(() => {
    const client = createSaasApiClient();
    initAnalytics(client, "tspace_web");
  }, []);
}
