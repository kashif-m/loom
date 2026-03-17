'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import Navigation from '../../../components/Navigation';
import PageHeader from '../../../components/PageHeader';
import { createTeam } from '../../../lib/api';

export default function CreateTeamPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  
  const [formData, setFormData] = useState({
    team_id: '',
    name: '',
    description: '',
    generalist_agent_id: '',
  });
  
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      router.push('/teams');
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to create team');
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (!formData.team_id || !formData.name) {
      setError('Team ID and name are required');
      return;
    }
    
    mutation.mutate(formData);
  };

  return (
    <div>
      <Navigation />
      
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link
            href="/teams"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Teams
          </Link>
        </div>

        <PageHeader 
          title="Create New Team" 
          subtitle="Organize agents into teams"
        />

        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-6 bg-white shadow rounded-lg p-6">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
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
              <p className="mt-1 text-xs text-gray-500">Unique identifier, no spaces</p>
            </div>

            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Team Name *
              </label>
              <input
                type="text"
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                placeholder="e.g., Engineering Team"
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
              placeholder="What does this team do?"
            />
          </div>

          <div>
            <label htmlFor="generalist_agent_id" className="block text-sm font-medium text-gray-700">
              Team Lead (Generalist)
            </label>
            <input
              type="text"
              id="generalist_agent_id"
              value={formData.generalist_agent_id}
              onChange={(e) => setFormData({ ...formData, generalist_agent_id: e.target.value })}
              className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
              placeholder="e.g., engineering_lead (optional)"
            />
            <p className="mt-1 text-xs text-gray-500">Agent ID of the team lead generalist (optional)</p>
          </div>

          <div className="pt-6 border-t border-gray-200 flex items-center justify-end space-x-3">
            <Link
              href="/teams"
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50"
            >
              {mutation.isPending ? 'Creating...' : 'Create Team'}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
