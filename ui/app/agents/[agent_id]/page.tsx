'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Power, PowerOff, Edit2, Save, X, User, Settings } from 'lucide-react';
import Navigation from '../../../components/Navigation';
import PageHeader from '../../../components/PageHeader';
import LoadingSpinner from '../../../components/LoadingSpinner';
import ErrorMessage from '../../../components/ErrorMessage';
import { getAgent, updateAgent, activateAgent, deactivateAgent } from '../../../lib/api';
import { Agent } from '../../../lib/types';

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const agentId = params.agent_id as string;
  
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<Agent>>({});

  const { data: agent, isLoading, error } = useQuery({
    queryKey: ['agent', agentId],
    queryFn: () => getAgent(agentId),
  });

  const updateMutation = useMutation({
    mutationFn: (updates: Partial<Agent>) => updateAgent(agentId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent', agentId] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setIsEditing(false);
    },
  });

  const activateMutation = useMutation({
    mutationFn: () => activateAgent(agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent', agentId] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: () => deactivateAgent(agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent', agentId] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const handleSave = () => {
    updateMutation.mutate(editData);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditData({});
  };

  const getRoleLabel = (level: string) => {
    switch (level) {
      case 'kr': return 'Kite Runner';
      case 'generalist': return 'Team Lead';
      case 'specialist': return 'Specialist';
      default: return level;
    }
  };

  if (isLoading) {
    return (
      <div>
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-center py-12">
            <LoadingSpinner />
          </div>
        </main>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div>
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <ErrorMessage message="Failed to load agent" />
        </main>
      </div>
    );
  }

  return (
    <div>
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link
            href="/agents"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Agents
          </Link>
        </div>

        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <div className={`p-3 rounded-lg ${agent.active ? 'bg-amber-100' : 'bg-gray-100'}`}>
              <User className={`h-8 w-8 ${agent.active ? 'text-amber-600' : 'text-gray-500'}`} />
            </div>
            <div className="ml-4">
              <PageHeader 
                title={agent.name} 
                subtitle={agent.agent_id}
              />
              <div className="mt-1 flex items-center space-x-2">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {getRoleLabel(agent.authority_level)}
                </span>
                {agent.active ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    Active
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                    Inactive
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {isEditing ? (
              <>
                <button
                  onClick={handleCancel}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                >
                  <X className="h-4 w-4 mr-1" />
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                  className="inline-flex items-center px-3 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-amber-600 hover:bg-amber-700"
                >
                  <Save className="h-4 w-4 mr-1" />
                  Save Changes
                </button>
              </>
            ) : (
              <>
                {agent.active ? (
                  <button
                    onClick={() => deactivateMutation.mutate()}
                    disabled={deactivateMutation.isPending}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50"
                  >
                    <PowerOff className="h-4 w-4 mr-1" />
                    Deactivate
                  </button>
                ) : (
                  <button
                    onClick={() => activateMutation.mutate()}
                    disabled={activateMutation.isPending}
                    className="inline-flex items-center px-3 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
                  >
                    <Power className="h-4 w-4 mr-1" />
                    Activate
                  </button>
                )}
                <button
                  onClick={() => {
                    setEditData({ ...agent });
                    setIsEditing(true);
                  }}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                >
                  <Edit2 className="h-4 w-4 mr-1" />
                  Edit
                </button>
              </>
            )}
          </div>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Configuration */}
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Configuration</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Team</label>
                {isEditing ? (
                  <input
                    type="text"
                    value={editData.team_id || ''}
                    onChange={(e) => setEditData({ ...editData, team_id: e.target.value })}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                  />
                ) : (
                  <p className="mt-1 text-sm text-gray-900">{agent.team_id || 'Unassigned'}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Model Role</label>
                {isEditing ? (
                  <select
                    value={editData.model_role || 'reasoning'}
                    onChange={(e) => setEditData({ ...editData, model_role: e.target.value })}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                  >
                    <option value="fast">Fast (Haiku)</option>
                    <option value="reasoning">Reasoning (Sonnet)</option>
                  </select>
                ) : (
                  <p className="mt-1 text-sm text-gray-900 capitalize">{agent.model_role}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Memory Access</label>
                {isEditing ? (
                  <select
                    value={editData.memory_scope || 'agentic_only'}
                    onChange={(e) => setEditData({ ...editData, memory_scope: e.target.value })}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                  >
                    <option value="agentic_only">Agent only</option>
                    <option value="agentic_and_team">Team memory</option>
                    <option value="agentic_team_and_org">Org memory</option>
                  </select>
                ) : (
                  <p className="mt-1 text-sm text-gray-900">{agent.memory_scope.replace(/_/g, ' ')}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Max Retries</label>
                {isEditing ? (
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={editData.max_retries || 3}
                    onChange={(e) => setEditData({ ...editData, max_retries: parseInt(e.target.value) })}
                    className="mt-1 block w-32 border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                  />
                ) : (
                  <p className="mt-1 text-sm text-gray-900">{agent.max_retries}</p>
                )}
              </div>
            </div>
          </div>

          {/* Tools */}
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Permitted Tools</h3>
            
            {agent.permitted_tools?.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {agent.permitted_tools.map((tool) => (
                  <span
                    key={tool}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-amber-100 text-amber-800"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No tools assigned</p>
            )}
          </div>
        </div>

        {/* Description */}
        {agent.description && (
          <div className="mt-6 bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Description</h3>
            {isEditing ? (
              <textarea
                rows={4}
                value={editData.description || ''}
                onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                className="block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
              />
            ) : (
              <p className="text-sm text-gray-600">{agent.description}</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
