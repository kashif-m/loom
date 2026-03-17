'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { Plus, Users, UserCheck, ChevronRight, Trash2 } from 'lucide-react';
import Navigation from '../../components/Navigation';
import PageHeader from '../../components/PageHeader';
import LoadingSpinner from '../../components/LoadingSpinner';
import ErrorMessage from '../../components/ErrorMessage';
import EmptyState from '../../components/EmptyState';
import { getTeams, deleteTeam } from '../../lib/api';
import { Team } from '../../lib/types';

function TeamCard({ team }: { team: Team }) {
  const queryClient = useQueryClient();
  
  const deleteMutation = useMutation({
    mutationFn: () => deleteTeam(team.team_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
  });

  return (
    <div className="bg-white rounded-lg shadow hover:shadow-md transition-shadow">
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <div className="p-2 rounded-lg bg-blue-100">
              <Users className="h-5 w-5 text-blue-600" />
            </div>
            <div className="ml-3">
              <h3 className="text-lg font-medium text-gray-900">
                <Link href={`/teams/${team.team_id}`} className="hover:text-amber-600">
                  {team.name}
                </Link>
              </h3>
              <p className="text-sm text-gray-500">{team.team_id}</p>
            </div>
          </div>
          <button
            onClick={() => {
              if (confirm(`Delete team "${team.name}"?`)) {
                deleteMutation.mutate();
              }
            }}
            disabled={deleteMutation.isPending}
            className="text-gray-400 hover:text-red-600"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>

        {team.description && (
          <p className="mt-3 text-sm text-gray-600 line-clamp-2">{team.description}</p>
        )}

        <div className="mt-4 flex items-center space-x-6 text-sm">
          <div className="flex items-center">
            <UserCheck className="h-4 w-4 text-gray-400 mr-1" />
            <span className="text-gray-600">
              {team.generalist_agent_id ? 'Has lead' : 'No lead'}
            </span>
          </div>
          <div className="flex items-center">
            <Users className="h-4 w-4 text-gray-400 mr-1" />
            <span className="text-gray-600">
              {team.specialist_count || 0} specialists
            </span>
          </div>
        </div>

        <div className="mt-4">
          <Link 
            href={`/teams/${team.team_id}`}
            className="inline-flex items-center text-sm font-medium text-amber-600 hover:text-amber-700"
          >
            Manage Team
            <ChevronRight className="ml-1 h-4 w-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function TeamsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['teams'],
    queryFn: getTeams,
  });

  const teams = data?.teams || [];

  return (
    <div>
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between">
          <PageHeader 
            title="Teams" 
            subtitle="Manage teams and agent assignments"
          />
          <Link
            href="/teams/new"
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-amber-600 hover:bg-amber-700"
          >
            <Plus className="h-4 w-4 mr-2" />
            Create Team
          </Link>
        </div>

        {/* Stats */}
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-3">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Users className="h-6 w-6 text-gray-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Total Teams</dt>
                    <dd className="text-2xl font-semibold text-gray-900">{teams.length}</dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <UserCheck className="h-6 w-6 text-blue-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">With Team Lead</dt>
                    <dd className="text-2xl font-semibold text-gray-900">
                      {teams.filter(t => t.generalist_agent_id).length}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Users className="h-6 w-6 text-green-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Total Specialists</dt>
                    <dd className="text-2xl font-semibold text-gray-900">
                      {teams.reduce((sum, t) => sum + (t.specialist_count || 0), 0)}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Teams Grid */}
        <div className="mt-6">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          ) : error ? (
            <ErrorMessage message="Failed to load teams" />
          ) : teams.length === 0 ? (
            <EmptyState
              icon={<Users className="h-12 w-12" />}
              title="No teams found"
              description="Create your first team to organize agents"
            />
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {teams.map((team: Team) => (
                <TeamCard key={team.team_id} team={team} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
