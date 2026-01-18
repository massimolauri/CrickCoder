import { apiClient, buildProjectQuery, API_BASE_URL } from './apiClient';
import type { ApiResult, TemplatesResponse, LLMSettings } from '@/types/api.types';

export const templateService = {
    /**
     * Recupera la lista dei template installati
     */
    async listTemplates(projectPath: string): Promise<ApiResult<TemplatesResponse>> {
        return apiClient.get<TemplatesResponse>(
            '/templates',
            buildProjectQuery(projectPath)
        );
    },

    /**
     * Uploads a new template ZIP with LLM Settings for AI Indexing
     */
    async uploadTemplate(file: File, projectPath: string, llmSettings: LLMSettings): Promise<void> {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('project_path', projectPath);
        formData.append('llm_settings', JSON.stringify(llmSettings));

        // Use fetch directly for EventStream/Multipart
        const response = await fetch(`${API_BASE_URL}/templates/upload`, {
            method: 'POST',
            body: formData,
            // Header Content-Type is auto-set by browser for FormData (multipart/form-data boundary)
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
        }

        return; // The caller handles the stream (or we could handle it here, but usually UI handles stream)
    }
};
