import { useState, useEffect } from 'react';
import { toast } from 'sonner';

interface ModelType {
  name: string;
  models: string[];
}

export function useModelFetch() {
  const [providers, setProviders] = useState<ModelType[]>([]);

  useEffect(() => {
    async function fetchModels() {
      try {
        const response = await fetch(
          `http://${process.env.LLMSTUDIO_ENGINE_HOST || 'localhost'}:${
            process.env.LLMSTUDIO_ENGINE_PORT || '8000'
          }/api/engine/models`
        );
        const data = await response.json();
        const fetchedProviders: ModelType[] = Object.keys(data).map((key) => ({
          name: data[key].name,
          models: data[key].models.map(
            (modelName: string, index: number) => modelName
          ),
        }));
        setProviders(fetchedProviders);
      } catch (e) {
        toast.error('LLMstudio Engine is not running');
      }
    }

    fetchModels();
  }, []);

  return { providers };
}
