'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Plus, Trash2 } from 'lucide-react';
import Navigation from '../../../components/Navigation';
import PageHeader from '../../../components/PageHeader';
import { createAgent } from '../../../lib/api';

export default function CreateAgentPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  
  const [formData, setFormData] = useState({
    agent_id: '',
    name: '',
    authority_level: 'specialist',
    team_id: '',
    model_role: 'reasoning',
    permitted_tools: [] as string[],
    memory_scope: 'agentic_only',
    description: '',
    max_retries: 3,
  });
  
  const [toolInput, setToolInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      router.push('/agents');
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to create agent');
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (!formData.agent_id || !formData.name || !formData.team_id) {
      setError('Agent ID, name, and team are required');
      return;
    }
    
    mutation.mutate(formData);
  };

  const addTool = () => {
    if (toolInput.trim() && !formData.permitted_tools.includes(toolInput.trim())) {
      setFormData({
        ...formData,
        permitted_tools: [...formData.permitted_tools, toolInput.trim()],
      });
      setToolInput('');
    }
  };

  const removeTool = (tool: string) => {
    setFormData({
      ...formData,
      permitted_tools: formData.permitted_tools.filter(t => t !== tool),
    });
  };

  return (
    <div>
      <Navigation />
      
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link
            href="/agents"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Agents
          </Link>
        </div>

        <PageHeader 
          title="Create New Agent" 
          subtitle="Configure a new agent for your organization"
        />

        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-6 bg-white shadow rounded-lg p-6">
          {/* Basic Info */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-gray-900">Basic Information</h3>
            
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="agent_id" className="block text-sm font-medium text-gray-700">
                  Agent ID *
                </label>
                <input
                  type="text"
                  id="agent_id"
                  value={formData.agent_id}
                  onChange={(e) => setFormData({ ...formData, agent_id: e.target.value })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                  placeholder="e.g., frontend_specialist"
                  required
                />
                <p className="mt-1 text-xs text-gray-500">Unique identifier, no spaces</p>
              </div>

              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                  Name *
                </label>
                <input
                  type="text"
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                  placeholder="e.g., Frontend Specialist"
                  required
                />
              </div>
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                id="description"
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                placeholder="What does this agent do?"
              />
            </div>
          </div>

          {/* Role & Team */}
          <div className="space-y-4 pt-6 border-t border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Role & Assignment</h3>
            
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="authority_level" className="block text-sm font-medium text-gray-700">
                  Authority Level *
                </label>
                <select
                  id="authority_level"
                  value={formData.authority_level}
                  onChange={(e) => setFormData({ ...formData, authority_level: e.target.value })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                >
                  <option value="kr">Kite Runner (Org)</option>
                  <option value="generalist">Team Lead</option>
                  <option value="specialist">Specialist</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  {formData.authority_level === 'kr' && 'Organizational orchestrator, routes tasks to teams'}
                  {formData.authority_level === 'generalist' && 'Team leader, delegates to specialists'}
                  {formData.authority_level === 'specialist' && 'Task executor with tools'}
                </p>
              </div>

              <div>
                <label htmlFor="team_id" className="block text-sm font-medium text-gray-700">
                  Team ID *
                </label>
                <input
                  type="text"
                  id="team_id"
                  value={formData.team_id}
                  onChange={(e) => setFormData({ ...formData, team_id: e.target.value })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                  placeholder="e.g., engineering"
                  required
                />
              </div>
            </div>
          </div>

          {/* Configuration */}
          <div className="space-y-4 pt-6 border-t border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Configuration</h3>
            
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="model_role" className="block text-sm font-medium text-gray-700">
                  Model Role
                </label>
                <select
                  id="model_role"
                  value={formData.model_role}
                  onChange={(e) => setFormData({ ...formData, model_role: e.target.value })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                >
                  <option value="fast">Fast (Haiku) — quick operations</option>
                  <option value="reasoning">Reasoning (Sonnet) — complex tasks</option>
                </select>
              </div>

              <div>
                <label htmlFor="memory_scope" className="block text-sm font-medium text-gray-700">
                  Memory Access
                </label>
                <select
                  id="memory_scope"
                  value={formData.memory_scope}
                  onChange={(e) => setFormData({ ...formData, memory_scope: e.target.value })}
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                >
                  <option value="agentic_only">Agent only</option>
                  <option value="agentic_and_team">Team memory</option>
                  <option value="agentic_team_and_org">Org memory</option>
                </select>
              </div>
            </div>

            <div>
              <label htmlFor="max_retries" className="block text-sm font-medium text-gray-700">
                Max Retries
              </label>
              <input
                type="number"
                id="max_retries"
                min={1}
                max={10}
                value={formData.max_retries}
                onChange={(e) => setFormData({ ...formData, max_retries: parseInt(e.target.value) })}
                className="mt-1 block w-32 border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">Maximum retry attempts before escalation</p>
            </div>
          </div>

          {/* Tools */}
          <div className="space-y-4 pt-6 border-t border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Permitted Tools</h3>
            
            <div className="flex space-x-2">
              <input
                type="text"
                value={toolInput}
                onChange={(e) => setToolInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTool())}
                className="flex-1 border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                placeholder="Enter tool name (e.g., file_read, git_commit)"
              />
              <button
                type="button"
                onClick={addTool}
                className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>

            {formData.permitted_tools.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {formData.permitted_tools.map((tool) => (
                  <span
                    key={tool}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"
                  >
                    {tool}
                    <button
                      type="button"
                      onClick={() => removeTool(tool)}
                      className="ml-1 text-amber-600 hover:text-amber-900"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="pt-6 border-t border-gray-200 flex items-center justify-end space-x-3">
            <Link
              href="/agents"
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50"
            >
              {mutation.isPending ? 'Creating...' : 'Create Agent'}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
