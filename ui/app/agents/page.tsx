'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { Plus, Users, User, Settings, ChevronRight, Power, PowerOff } from 'lucide-react';
import Navigation from '../../components/Navigation';
import PageHeader from '../../components/PageHeader';
import StatusBadge from '../../components/StatusBadge';
import LoadingSpinner from '../../components/LoadingSpinner';
import ErrorMessage from '../../components/ErrorMessage';
import EmptyState from '../../components/EmptyState';
import { getAgents, activateAgent, deactivateAgent } from '../../lib/api';
import { Agent } from '../../lib/types';

function AgentCard({ agent }: { agent: Agent }) {
  const queryClient = useQueryClient();
  
  const activateMutation = useMutation({
    mutationFn: () => activateAgent(agent.agent_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
  
  const deactivateMutation = useMutation({
    mutationFn: () => deactivateAgent(agent.agent_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const getRoleColor = (level: string) => {
    switch (level) {
      case 'kr': return 'bg-purple-100 text-purple-800';
      case 'generalist': return 'bg-blue-100 text-blue-800';
      case 'specialist': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getRoleLabel = (level: string) => {
    switch (level) {
      case 'kr': return 'Kite Runner';
      case 'generalist': return 'Team Lead';
      case 'specialist': return 'Specialist';
      default: return level;
    }
  };

  return (
    <div className={`bg-white rounded-lg shadow hover:shadow-md transition-shadow border-l-4 ${
      agent.active ? 'border-green-400' : 'border-gray-300'
    }`}>
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <div className={`p-2 rounded-lg ${agent.active ? 'bg-amber-100' : 'bg-gray-100'}`}>
              <User className={`h-5 w-5 ${agent.active ? 'text-amber-600' : 'text-gray-500'}`} />
            </div>
            <div className="ml-3">
              <h3 className="text-lg font-medium text-gray-900">
                <Link href={`/agents/${agent.agent_id}`} className="hover:text-amber-600">
                  {agent.name}
                </Link>
              </h3>
              <p className="text-sm text-gray-500">{agent.agent_id}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleColor(agent.authority_level)}`}>
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

        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Team:</span>
            <span className="ml-2 text-gray-900">{agent.team_id || 'Unassigned'}</span>
          </div>
          <div>
            <span className="text-gray-500">Model:</span>
            <span className="ml-2 text-gray-900 capitalize">{agent.model_role}</span>
          </div>
          <div>
            <span className="text-gray-500">Memory:</span>
            <span className="ml-2 text-gray-900">{agent.memory_scope?.replace(/_/g, ' ') || 'Agent only'}</span>
          </div>
          <div>
            <span className="text-gray-500">Tools:</span>
            <span className="ml-2 text-gray-900">{agent.permitted_tools?.length || 0}</span>
          </div>
        </div>

        {agent.description && (
          <p className="mt-3 text-sm text-gray-600 line-clamp-2">{agent.description}</p>
        )}

        <div className="mt-4 flex items-center justify-between">
          <Link 
            href={`/agents/${agent.agent_id}`}
            className="inline-flex items-center text-sm font-medium text-amber-600 hover:text-amber-700"
          >
            View Details
            <ChevronRight className="ml-1 h-4 w-4" />
          </Link>
          
          {agent.active ? (
            <button
              onClick={() => deactivateMutation.mutate()}
              disabled={deactivateMutation.isPending}
              className="inline-flex items-center text-sm text-red-600 hover:text-red-700"
            >
              <PowerOff className="h-4 w-4 mr-1" />
              Deactivate
            </button>
          ) : (
            <button
              onClick={() => activateMutation.mutate()}
              disabled={activateMutation.isPending}
              className="inline-flex items-center text-sm text-green-600 hover:text-green-700"
            >
              <Power className="h-4 w-4 mr-1" />
              Activate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const [filterRole, setFilterRole] = useState<string>('all');
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['agents'],
    queryFn: getAgents,
  });

  const agents = data?.agents || [];
  
  const filteredAgents = filterRole === 'all' 
    ? agents 
    : agents.filter(a => a.authority_level === filterRole);

  const krCount = agents.filter(a => a.authority_level === 'kr').length;
  const generalistCount = agents.filter(a => a.authority_level === 'generalist').length;
  const specialistCount = agents.filter(a => a.authority_level === 'specialist').length;

  return (
    <div>
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between">
          <PageHeader 
            title="Agents" 
            subtitle="Manage agents and their capabilities"
          />
          <Link
            href="/agents/new"
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-amber-600 hover:bg-amber-700"
          >
            <Plus className="h-4 w-4 mr-2" />
            Create Agent
          </Link>
        </div>

        {/* Stats */}
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-4">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Users className="h-6 w-6 text-gray-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Total Agents</dt>
                    <dd className="text-2xl font-semibold text-gray-900">{agents.length}</dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Settings className="h-6 w-6 text-purple-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Kite Runners</dt>
                    <dd className="text-2xl font-semibold text-gray-900">{krCount}</dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <User className="h-6 w-6 text-blue-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Team Leads</dt>
                    <dd className="text-2xl font-semibold text-gray-900">{generalistCount}</dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <User className="h-6 w-6 text-green-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Specialists</dt>
                    <dd className="text-2xl font-semibold text-gray-900">{specialistCount}</dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="mt-6 flex items-center space-x-4">
          <span className="text-sm font-medium text-gray-700">Filter by role:</span>
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            className="mt-1 block w-48 pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-amber-500 focus:border-amber-500 sm:text-sm rounded-md"
          >
            <option value="all">All Roles</option>
            <option value="kr">Kite Runner</option>
            <option value="generalist">Team Lead</option>
            <option value="specialist">Specialist</option>
          </select>
        </div>

        {/* Agent Grid */}
        <div className="mt-6">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          ) : error ? (
            <ErrorMessage message="Failed to load agents" />
          ) : filteredAgents.length === 0 ? (
            <EmptyState
              icon={<Users className="h-12 w-12" />}
              title="No agents found"
              description={filterRole === 'all' ? "Create your first agent to get started" : "No agents match the selected filter"}
            />
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {filteredAgents.map((agent: Agent) => (
                <AgentCard key={agent.agent_id} agent={agent} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
