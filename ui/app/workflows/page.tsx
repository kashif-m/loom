'use client';

import Link from 'next/link';
import { useQuery, useMutation } from '@tanstack/react-query';
import { FileText, Settings } from 'lucide-react';
import Navigation from '../../components/Navigation';
import PageHeader from '../../components/PageHeader';
import StatusBadge from '../../components/StatusBadge';
import LoadingSpinner from '../../components/LoadingSpinner';
import ErrorMessage from '../../components/ErrorMessage';
import EmptyState from '../../components/EmptyState';
import { getWorkflows, updateWorkflowStatus } from '../../lib/api';
import { Workflow } from '../../lib/types';

export default function Workflows() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['workflows'],
    queryFn: getWorkflows,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => 
      updateWorkflowStatus(id, status),
    onSuccess: () => refetch(),
  });

  const workflows = data?.workflows || [];

  return (
    <div>
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader 
          title="Workflows" 
          subtitle="View and manage workflow definitions"
        />

        <div className="bg-white shadow rounded-lg">
          {isLoading ? (
            <div className="p-8 flex justify-center">
              <LoadingSpinner />
            </div>
          ) : error ? (
            <div className="p-4">
              <ErrorMessage message="Failed to load workflows" />
            </div>
          ) : workflows.length === 0 ? (
            <EmptyState
              icon={<FileText className="h-12 w-12" />}
              title="No workflows"
              description="Workflows will appear here once loaded"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Workflow
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Level
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Version
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {workflows.map((workflow: Workflow) => (
                    <tr 
                      key={`${workflow.id}:${workflow.version}`}
                      className={`hover:bg-gray-50 ${workflow.status === 'draft' ? 'border-l-4 border-amber-400' : ''}`}
                    >
                      <td className="px-6 py-4">
                        <Link 
                          href={`/workflows/${encodeURIComponent(workflow.id)}`}
                          className="text-sm font-medium text-amber-600 hover:text-amber-900"
                        >
                          {workflow.id}
                        </Link>
                        <p className="text-xs text-gray-500 mt-1">{workflow.trigger}</p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {workflow.level}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <StatusBadge status={workflow.status} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {workflow.version}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {workflow.status === 'draft' && (
                          <button
                            onClick={() => updateMutation.mutate({ id: workflow.id, status: 'active' })}
                            disabled={updateMutation.isPending}
                            className="text-green-600 hover:text-green-900 font-medium"
                          >
                            Approve
                          </button>
                        )}
                        {workflow.status === 'active' && (
                          <button
                            onClick={() => updateMutation.mutate({ id: workflow.id, status: 'deprecated' })}
                            disabled={updateMutation.isPending}
                            className="text-gray-600 hover:text-gray-900 font-medium"
                          >
                            Deprecate
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
