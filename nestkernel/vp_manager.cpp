/*
 *  vp_manager.cpp
 *
 *  This file is part of NEST.
 *
 *  Copyright (C) 2004 The NEST Initiative
 *
 *  NEST is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  NEST is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with NEST.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

#include "vp_manager.h"

// C++ includes:
#include <cstdlib>

// Includes from libnestutil:
#include "logging.h"

// Includes from nestkernel:
#include "kernel_manager.h"
#include "mpi_manager.h"
#include "mpi_manager_impl.h"
#include "vp_manager_impl.h"

// Includes from sli:
#include "dictutils.h"

nest::VPManager::VPManager()
#ifdef _OPENMP
  : force_singlethreading_( false )
#else
  : force_singlethreading_( true )
#endif
  , n_threads_( 1 )
{
}

void
nest::VPManager::initialize( const bool reset_kernel )
{
  if ( not reset_kernel )
  {
    return;
  }

// When the VPManager is initialized, you will have 1 thread again.
// Setting more threads will be done via nest::set_kernel_status
#ifdef _OPENMP
  // The next line is required because we use the OpenMP
  // threadprivate() directive in the allocator, see OpenMP
  // API Specifications v 3.1, Ch 2.9.2, p 89, l 14f.
  // It keeps OpenMP from automagically changing the number
  // of threads used for parallel regions.
  omp_set_dynamic( false );
#endif

  if ( get_OMP_NUM_THREADS() > 1 )
  {
    std::string msg = "OMP_NUM_THREADS is set in your environment, but NEST ignores it.\n";
    msg += "For details, see the Guide to parallel computing in the NEST Documentation.";

    LOG( M_INFO, "VPManager::initialize()", msg );
  }

  set_num_threads( 1 );
}

void
nest::VPManager::finalize( const bool )
{
}

size_t
nest::VPManager::get_OMP_NUM_THREADS() const
{
  const char* const omp_num_threads = std::getenv( "OMP_NUM_THREADS" );
  if ( omp_num_threads )
  {
    return std::atoi( omp_num_threads );
  }
  else
  {
    return 0;
  }
}

void
nest::VPManager::set_status( const DictionaryDatum& d )
{
  size_t n_threads = get_num_threads();
  size_t n_vps = get_num_virtual_processes();

  bool n_threads_updated = updateValue< long >( d, names::local_num_threads, n_threads );
  bool n_vps_updated = updateValue< long >( d, names::total_num_virtual_procs, n_vps );

  if ( n_vps_updated )
  {
    if ( not n_threads_updated )
    {
      n_threads = n_vps / kernel().mpi_manager.get_num_processes();
    }

    const bool n_threads_conflict = n_vps / kernel().mpi_manager.get_num_processes() != n_threads;
    const bool n_procs_conflict = n_vps % kernel().mpi_manager.get_num_processes() != 0;
    if ( n_threads_conflict or n_procs_conflict )
    {
      throw BadProperty(
        "Requested total_num_virtual_procs is incompatible with the number of processes and threads."
        "It must be an integer multiple of num_processes and equal to "
        "local_num_threads * num_processes. Value unchanged." );
    }
  }

  // We only want to act if new values differ from the old
  n_threads_updated = n_threads != get_num_threads();
  n_vps_updated = n_vps != get_num_virtual_processes();

  if ( n_threads_updated or n_vps_updated )
  {
    std::vector< std::string > errors;
    if ( kernel().node_manager.size() > 0 )
    {
      errors.push_back( "Nodes exist" );
    }
    if ( kernel().connection_manager.get_user_set_delay_extrema() )
    {
      errors.push_back( "Delay extrema have been set" );
    }
    if ( kernel().simulation_manager.has_been_simulated() )
    {
      errors.push_back( "Network has been simulated" );
    }
    if ( kernel().model_manager.are_model_defaults_modified() )
    {
      errors.push_back( "Model defaults were modified" );
    }
    if ( kernel().sp_manager.is_structural_plasticity_enabled() and n_threads > 1 )
    {
      errors.push_back( "Structural plasticity enabled: multithreading cannot be enabled" );
    }
    if ( force_singlethreading_ and n_threads > 1 )
    {
      errors.push_back( "This installation of NEST does not support multiple threads" );
    }

    if ( not errors.empty() )
    {
      std::string msg = "Number of threads unchanged. Error conditions:";
      for ( auto& error : errors )
      {
        msg += " " + error + ".";
      }
      throw KernelException( msg );
    }

    if ( get_OMP_NUM_THREADS() > 0 and get_OMP_NUM_THREADS() != n_threads )
    {
      std::string msg = "OMP_NUM_THREADS is set in your environment, but NEST ignores it.\n";
      msg += "For details, see the Guide to parallel computing in the NEST Documentation.";
      LOG( M_WARNING, "VPManager::set_status()", msg );
    }

    kernel().change_number_of_threads( n_threads );
  }
}

void
nest::VPManager::get_status( DictionaryDatum& d )
{
  def< long >( d, names::local_num_threads, get_num_threads() );
  def< long >( d, names::total_num_virtual_procs, get_num_virtual_processes() );
}

void
nest::VPManager::set_num_threads( size_t n_threads )
{
  assert( not( kernel().sp_manager.is_structural_plasticity_enabled() and n_threads > 1 ) );
  n_threads_ = n_threads;

#ifdef _OPENMP
  omp_set_num_threads( n_threads_ );
#endif
}
