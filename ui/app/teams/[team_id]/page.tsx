'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Users, UserCheck, User, Plus, X } from 'lucide-react';
import Navigation from '../../../components/Navigation';
import PageHeader from '../../../components/PageHeader';
import LoadingSpinner from '../../../components/LoadingSpinner';
import ErrorMessage from '../../../components/ErrorMessage';
import { getTeam, getAgents, addAgentToTeam, removeAgentFromTeam } from '../../../lib/api';
import { Team, Agent } from '../../../lib/types';

export default function TeamDetailPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const teamId = params.team_id as string;

  const { data: team, isLoading: teamLoading, error: teamError } = useQuery({
    queryKey: ['team', teamId],
    queryFn: () => getTeam(teamId),
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: getAgents,
  });

  const allAgents = agentsData?.agents || [];
  
  // Find available specialists (not in any team)
  const availableSpecialists = allAgents.filter(
    (a: Agent) => a.authority_level === 'specialist' && 
                  a.team_id !== teamId &&
                  a.active
  );

  const addAgentMutation = useMutation({
    mutationFn: (agentId: string) => addAgentToTeam(teamId, agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team', teamId] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const removeAgentMutation = useMutation({
    mutationFn: (agentId: string) => removeAgentFromTeam(teamId, agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team', teamId] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  if (teamLoading) {
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

  if (teamError || !team) {
    return (
      <div>
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <ErrorMessage message="Failed to load team" />
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
            href="/teams"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Teams
          </Link>
        </div>

        <div className="flex items-center">
          <div className="p-3 rounded-lg bg-blue-100">
            <Users className="h-8 w-8 text-blue-600" />
          </div>
          <div className="ml-4">
            <PageHeader title={team.name} subtitle={team.team_id} />
            {team.description && (
              <p className="mt-1 text-sm text-gray-600">{team.description}</p>
            )}
          </div>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Team Lead */}
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Team Lead</h3>
            
            {team.generalist ? (
              <div className="flex items-center p-4 bg-blue-50 rounded-lg">
                <div className="p-2 rounded-full bg-blue-100">
                  <UserCheck className="h-5 w-5 text-blue-600" />
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-900">
                    <Link href={`/agents/${team.generalist.agent_id}`} className="hover:text-amber-600">
                      {team.generalist.name}
                    </Link>
                  </p>
                  <p className="text-xs text-gray-500">{team.generalist.agent_id}</p>
                </div>
                <span className="ml-auto inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                  Generalist
                </span>
              </div>
            ) : (
              <div className="text-center py-8 bg-gray-50 rounded-lg">
                <UserCheck className="h-12 w-12 text-gray-300 mx-auto" />
                <p className="mt-2 text-sm text-gray-500">No team lead assigned</p>
                <p className="text-xs text-gray-400">Assign a generalist agent as team lead</p>
              </div>
            )}
          </div>

          {/* Team Members */}
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">Specialists</h3>
              <span className="text-sm text-gray-500">
                {team.agents?.length || 0} members
              </span>
            </div>

            {team.agents && team.agents.length > 0 ? (
              <div className="space-y-2">
                {team.agents.map((agent: any) => (
                  <div key={agent.agent_id} className="flex items-center p-3 bg-gray-50 rounded-lg">
                    <div className="p-1.5 rounded-full bg-green-100">
                      <User className="h-4 w-4 text-green-600" />
                    </div>
                    <div className="ml-3 flex-1">
                      <p className="text-sm font-medium text-gray-900">
                        <Link href={`/agents/${agent.agent_id}`} className="hover:text-amber-600">
                          {agent.name}
                        </Link>
                      </p>
                      <p className="text-xs text-gray-500">{agent.agent_id}</p>
                    </div>
                    <button
                      onClick={() => removeAgentMutation.mutate(agent.agent_id)}
                      disabled={removeAgentMutation.isPending}
                      className="text-gray-400 hover:text-red-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 bg-gray-50 rounded-lg">
                <Users className="h-12 w-12 text-gray-300 mx-auto" />
                <p className="mt-2 text-sm text-gray-500">No specialists assigned</p>
              </div>
            )}
          </div>
        </div>

        {/* Add Specialists */}
        {availableSpecialists.length > 0 && (
          <div className="mt-6 bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Add Specialists</h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {availableSpecialists.map((agent: Agent) => (
                <button
                  key={agent.agent_id}
                  onClick={() => addAgentMutation.mutate(agent.agent_id)}
                  disabled={addAgentMutation.isPending}
                  className="flex items-center p-3 border border-gray-200 rounded-lg hover:border-amber-300 hover:bg-amber-50 transition-colors text-left"
                >
                  <Plus className="h-4 w-4 text-amber-600 mr-2" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{agent.name}</p>
                    <p className="text-xs text-gray-500">{agent.agent_id}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
