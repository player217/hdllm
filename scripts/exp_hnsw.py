"""
HNSW Parameter Optimization Experiments
Author: Claude Code
Date: 2025-01-27
Description: Phase 2B-2 - Experimental scripts for HNSW parameter tuning
"""

import asyncio
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Dict, Any
import time
import json
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from backend.vector.qdrant_extensions import (
    HNSWOptimizer,
    HNSWProfile,
    HNSWConfig,
    CollectionManager,
    QdrantBatchProcessor
)

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HNSWExperiment:
    """
    Comprehensive HNSW parameter experimentation
    """
    
    def __init__(self, client: QdrantClient):
        self.client = client
        self.results = []
        self.test_collection = "hnsw_test_collection"
    
    async def prepare_test_data(self, num_vectors: int = 10000, dim: int = 1024) -> Dict[str, Any]:
        """
        Prepare test dataset
        
        Args:
            num_vectors: Number of test vectors
            dim: Vector dimension
            
        Returns:
            Test data dictionary
        """
        logger.info(f"📊 Preparing test data: {num_vectors} vectors of dimension {dim}")
        
        # Generate synthetic data with clusters
        num_clusters = 10
        vectors = []
        payloads = []
        
        for cluster_id in range(num_clusters):
            cluster_size = num_vectors // num_clusters
            
            # Generate cluster center
            center = np.random.randn(dim)
            center = center / np.linalg.norm(center)
            
            # Generate cluster points
            for i in range(cluster_size):
                # Add noise to center
                noise = np.random.randn(dim) * 0.1
                vector = center + noise
                vector = vector / np.linalg.norm(vector)  # Normalize
                
                vectors.append(vector.tolist())
                payloads.append({
                    "cluster_id": cluster_id,
                    "point_id": len(vectors) - 1,
                    "text": f"Test document {len(vectors) - 1} in cluster {cluster_id}"
                })
        
        # Generate query vectors (one per cluster)
        query_vectors = []
        for cluster_id in range(num_clusters):
            idx = cluster_id * (num_vectors // num_clusters)
            query_vectors.append(vectors[idx])
        
        return {
            "vectors": vectors,
            "payloads": payloads,
            "query_vectors": query_vectors,
            "num_clusters": num_clusters,
            "dimension": dim
        }
    
    async def create_test_collection(self, dim: int = 1024) -> None:
        """Create test collection"""
        try:
            # Delete if exists
            self.client.delete_collection(self.test_collection)
        except:
            pass
        
        # Create new collection
        self.client.create_collection(
            collection_name=self.test_collection,
            vectors_config=VectorParams(
                size=dim,
                distance=Distance.COSINE
            )
        )
        logger.info(f"✅ Created test collection: {self.test_collection}")
    
    async def run_parameter_sweep(
        self,
        test_data: Dict[str, Any],
        m_values: List[int] = None,
        ef_construct_values: List[int] = None,
        ef_search_values: List[int] = None
    ) -> pd.DataFrame:
        """
        Run comprehensive parameter sweep
        
        Args:
            test_data: Test dataset
            m_values: M parameter values to test
            ef_construct_values: ef_construct values to test
            ef_search_values: ef_search values to test
            
        Returns:
            Results DataFrame
        """
        if m_values is None:
            m_values = [4, 8, 16, 32, 64]
        if ef_construct_values is None:
            ef_construct_values = [100, 200, 400]
        if ef_search_values is None:
            ef_search_values = [50, 100, 200, 400]
        
        results = []
        
        for m in m_values:
            for ef_construct in ef_construct_values:
                logger.info(f"🔬 Testing m={m}, ef_construct={ef_construct}")
                
                # Create collection with parameters
                await self.create_test_collection(dim=test_data["dimension"])
                
                # Configure HNSW
                config = HNSWConfig(
                    m=m,
                    ef_construct=ef_construct,
                    ef_search=100  # Default for indexing
                )
                
                optimizer = HNSWOptimizer(self.client)
                await optimizer.optimize_collection(
                    self.test_collection,
                    HNSWProfile.BALANCED
                )
                
                # Upload vectors
                batch_processor = QdrantBatchProcessor(
                    self.client,
                    self.test_collection,
                    batch_size=100
                )
                
                upload_start = time.time()
                upload_result = await batch_processor.upload_batch(
                    test_data["vectors"],
                    test_data["payloads"]
                )
                index_time = time.time() - upload_start
                
                # Wait for indexing
                await asyncio.sleep(2)
                
                # Get collection info
                info = self.client.get_collection(self.test_collection)
                memory_usage = info.payload_schema_info if hasattr(info, 'payload_schema_info') else 0
                
                # Test different ef_search values
                for ef_search in ef_search_values:
                    # Update search params
                    self.client.update_collection(
                        collection_name=self.test_collection,
                        hnsw_config={"ef": ef_search}
                    )
                    
                    # Run search tests
                    search_times = []
                    recalls = []
                    
                    for query_vector in test_data["query_vectors"]:
                        # Time search
                        start = time.time()
                        results_search = self.client.search(
                            collection_name=self.test_collection,
                            query_vector=query_vector,
                            limit=10
                        )
                        search_time = time.time() - start
                        search_times.append(search_time)
                        
                        # Calculate recall (simplified)
                        found_cluster = results_search[0].payload["cluster_id"] if results_search else -1
                        expected_cluster = test_data["query_vectors"].index(query_vector) % test_data["num_clusters"]
                        recalls.append(1.0 if found_cluster == expected_cluster else 0.0)
                    
                    # Calculate metrics
                    avg_search_time = np.mean(search_times) * 1000  # Convert to ms
                    p95_search_time = np.percentile(search_times, 95) * 1000
                    p99_search_time = np.percentile(search_times, 99) * 1000
                    avg_recall = np.mean(recalls)
                    
                    result = {
                        "m": m,
                        "ef_construct": ef_construct,
                        "ef_search": ef_search,
                        "index_time": index_time,
                        "avg_search_time_ms": avg_search_time,
                        "p95_search_time_ms": p95_search_time,
                        "p99_search_time_ms": p99_search_time,
                        "recall": avg_recall,
                        "memory_mb": memory_usage / (1024 * 1024) if memory_usage else 0,
                        "vectors_count": len(test_data["vectors"])
                    }
                    
                    results.append(result)
                    
                    logger.info(
                        f"  ef_search={ef_search}: "
                        f"avg={avg_search_time:.2f}ms, "
                        f"p95={p95_search_time:.2f}ms, "
                        f"recall={avg_recall:.3f}"
                    )
        
        return pd.DataFrame(results)
    
    def analyze_results(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze experiment results
        
        Args:
            df: Results DataFrame
            
        Returns:
            Analysis dictionary
        """
        analysis = {}
        
        # Best for speed
        best_speed = df.nsmallest(1, 'avg_search_time_ms').iloc[0]
        analysis['best_for_speed'] = {
            "m": int(best_speed['m']),
            "ef_construct": int(best_speed['ef_construct']),
            "ef_search": int(best_speed['ef_search']),
            "avg_search_time_ms": float(best_speed['avg_search_time_ms']),
            "recall": float(best_speed['recall'])
        }
        
        # Best for recall (accuracy)
        best_recall = df.nlargest(1, 'recall').iloc[0]
        analysis['best_for_recall'] = {
            "m": int(best_recall['m']),
            "ef_construct": int(best_recall['ef_construct']),
            "ef_search": int(best_recall['ef_search']),
            "avg_search_time_ms": float(best_recall['avg_search_time_ms']),
            "recall": float(best_recall['recall'])
        }
        
        # Best balanced (speed vs recall)
        df['score'] = df['recall'] / (df['avg_search_time_ms'] / 10)  # Normalize
        best_balanced = df.nlargest(1, 'score').iloc[0]
        analysis['best_balanced'] = {
            "m": int(best_balanced['m']),
            "ef_construct": int(best_balanced['ef_construct']),
            "ef_search": int(best_balanced['ef_search']),
            "avg_search_time_ms": float(best_balanced['avg_search_time_ms']),
            "recall": float(best_balanced['recall'])
        }
        
        # Parameter impact analysis
        analysis['parameter_impact'] = {
            "m_vs_speed": df.groupby('m')['avg_search_time_ms'].mean().to_dict(),
            "m_vs_recall": df.groupby('m')['recall'].mean().to_dict(),
            "ef_search_vs_speed": df.groupby('ef_search')['avg_search_time_ms'].mean().to_dict(),
            "ef_search_vs_recall": df.groupby('ef_search')['recall'].mean().to_dict()
        }
        
        return analysis
    
    def plot_results(self, df: pd.DataFrame, output_dir: str = "experiments/hnsw") -> None:
        """
        Generate visualization plots
        
        Args:
            df: Results DataFrame
            output_dir: Output directory for plots
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)
        
        # 1. Speed vs Recall tradeoff
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for m in df['m'].unique():
            subset = df[df['m'] == m]
            ax.scatter(subset['avg_search_time_ms'], subset['recall'], 
                      label=f'm={m}', alpha=0.7, s=50)
        
        ax.set_xlabel('Average Search Time (ms)')
        ax.set_ylabel('Recall')
        ax.set_title('HNSW Parameter Tradeoff: Speed vs Recall')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/speed_vs_recall.png", dpi=150)
        plt.close()
        
        # 2. Parameter heatmap
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # m vs ef_search for speed
        pivot_speed = df.pivot_table(
            values='avg_search_time_ms',
            index='m',
            columns='ef_search',
            aggfunc='mean'
        )
        sns.heatmap(pivot_speed, annot=True, fmt='.1f', cmap='RdYlGn_r', 
                   ax=axes[0, 0], cbar_kws={'label': 'ms'})
        axes[0, 0].set_title('Search Time by m and ef_search')
        
        # m vs ef_search for recall
        pivot_recall = df.pivot_table(
            values='recall',
            index='m',
            columns='ef_search',
            aggfunc='mean'
        )
        sns.heatmap(pivot_recall, annot=True, fmt='.3f', cmap='RdYlGn', 
                   ax=axes[0, 1], cbar_kws={'label': 'recall'})
        axes[0, 1].set_title('Recall by m and ef_search')
        
        # ef_construct impact
        pivot_index = df.pivot_table(
            values='index_time',
            index='m',
            columns='ef_construct',
            aggfunc='mean'
        )
        sns.heatmap(pivot_index, annot=True, fmt='.1f', cmap='RdYlGn_r',
                   ax=axes[1, 0], cbar_kws={'label': 'seconds'})
        axes[1, 0].set_title('Index Time by m and ef_construct')
        
        # P95 latency
        pivot_p95 = df.pivot_table(
            values='p95_search_time_ms',
            index='m',
            columns='ef_search',
            aggfunc='mean'
        )
        sns.heatmap(pivot_p95, annot=True, fmt='.1f', cmap='RdYlGn_r',
                   ax=axes[1, 1], cbar_kws={'label': 'ms'})
        axes[1, 1].set_title('P95 Search Time by m and ef_search')
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/parameter_heatmaps.png", dpi=150)
        plt.close()
        
        # 3. Distribution plots
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        # Search time distribution
        df.boxplot(column='avg_search_time_ms', by='m', ax=axes[0])
        axes[0].set_title('Search Time Distribution by m')
        axes[0].set_ylabel('Search Time (ms)')
        
        # Recall distribution  
        df.boxplot(column='recall', by='ef_search', ax=axes[1])
        axes[1].set_title('Recall Distribution by ef_search')
        axes[1].set_ylabel('Recall')
        
        # Index time by ef_construct
        df.boxplot(column='index_time', by='ef_construct', ax=axes[2])
        axes[2].set_title('Index Time by ef_construct')
        axes[2].set_ylabel('Index Time (seconds)')
        
        plt.suptitle('')  # Remove default title
        plt.tight_layout()
        plt.savefig(f"{output_dir}/distributions.png", dpi=150)
        plt.close()
        
        logger.info(f"📈 Plots saved to {output_dir}/")
    
    def save_results(self, df: pd.DataFrame, analysis: Dict[str, Any], 
                    output_dir: str = "experiments/hnsw") -> None:
        """
        Save results to files
        
        Args:
            df: Results DataFrame
            analysis: Analysis dictionary
            output_dir: Output directory
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Save raw data
        df.to_csv(f"{output_dir}/raw_results.csv", index=False)
        
        # Save analysis
        with open(f"{output_dir}/analysis.json", 'w') as f:
            json.dump(analysis, f, indent=2)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(analysis)
        with open(f"{output_dir}/recommendations.md", 'w') as f:
            f.write(recommendations)
        
        logger.info(f"💾 Results saved to {output_dir}/")
    
    def generate_recommendations(self, analysis: Dict[str, Any]) -> str:
        """
        Generate parameter recommendations
        
        Args:
            analysis: Analysis results
            
        Returns:
            Markdown formatted recommendations
        """
        md = "# HNSW Parameter Recommendations\n\n"
        md += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        md += "## Optimal Configurations\n\n"
        
        md += "### 🏃 Best for Speed\n"
        speed = analysis['best_for_speed']
        md += f"- **Parameters**: m={speed['m']}, ef_construct={speed['ef_construct']}, ef_search={speed['ef_search']}\n"
        md += f"- **Performance**: {speed['avg_search_time_ms']:.2f}ms average search time\n"
        md += f"- **Recall**: {speed['recall']:.3f}\n"
        md += "- **Use Case**: Real-time applications, high query volume\n\n"
        
        md += "### 🎯 Best for Accuracy\n"
        recall = analysis['best_for_recall']
        md += f"- **Parameters**: m={recall['m']}, ef_construct={recall['ef_construct']}, ef_search={recall['ef_search']}\n"
        md += f"- **Performance**: {recall['avg_search_time_ms']:.2f}ms average search time\n"
        md += f"- **Recall**: {recall['recall']:.3f}\n"
        md += "- **Use Case**: Critical accuracy requirements, offline processing\n\n"
        
        md += "### ⚖️ Best Balanced\n"
        balanced = analysis['best_balanced']
        md += f"- **Parameters**: m={balanced['m']}, ef_construct={balanced['ef_construct']}, ef_search={balanced['ef_search']}\n"
        md += f"- **Performance**: {balanced['avg_search_time_ms']:.2f}ms average search time\n"
        md += f"- **Recall**: {balanced['recall']:.3f}\n"
        md += "- **Use Case**: General purpose RAG systems, balanced requirements\n\n"
        
        md += "## Parameter Impact Analysis\n\n"
        
        md += "### M Parameter\n"
        md += "- Controls graph connectivity and memory usage\n"
        md += "- Higher values improve recall but increase memory and search time\n"
        md += "- Recommended range: 16-32 for most applications\n\n"
        
        md += "### ef_construct Parameter\n"
        md += "- Affects index quality and build time\n"
        md += "- Higher values improve recall but significantly increase indexing time\n"
        md += "- Recommended: 200 for balanced performance\n\n"
        
        md += "### ef_search Parameter\n"
        md += "- Controls search accuracy vs speed tradeoff\n"
        md += "- Can be adjusted dynamically without reindexing\n"
        md += "- Recommended: 100-200 for production systems\n\n"
        
        return md


async def main():
    """Run HNSW experiments"""
    # Initialize client
    client = QdrantClient(host="localhost", port=6333)
    
    # Create experiment runner
    experiment = HNSWExperiment(client)
    
    # Prepare test data
    test_data = await experiment.prepare_test_data(
        num_vectors=5000,  # Reduced for faster testing
        dim=1024
    )
    
    logger.info("🚀 Starting HNSW parameter experiments...")
    
    # Run parameter sweep
    results_df = await experiment.run_parameter_sweep(
        test_data,
        m_values=[8, 16, 32],
        ef_construct_values=[100, 200],
        ef_search_values=[50, 100, 200]
    )
    
    # Analyze results
    analysis = experiment.analyze_results(results_df)
    
    # Generate plots
    experiment.plot_results(results_df)
    
    # Save results
    experiment.save_results(results_df, analysis)
    
    # Print summary
    print("\n" + "="*50)
    print("EXPERIMENT SUMMARY")
    print("="*50)
    print(f"\nBest for Speed:")
    print(f"  Config: m={analysis['best_for_speed']['m']}, "
          f"ef_search={analysis['best_for_speed']['ef_search']}")
    print(f"  Speed: {analysis['best_for_speed']['avg_search_time_ms']:.2f}ms")
    print(f"  Recall: {analysis['best_for_speed']['recall']:.3f}")
    
    print(f"\nBest for Recall:")
    print(f"  Config: m={analysis['best_for_recall']['m']}, "
          f"ef_search={analysis['best_for_recall']['ef_search']}")
    print(f"  Speed: {analysis['best_for_recall']['avg_search_time_ms']:.2f}ms")
    print(f"  Recall: {analysis['best_for_recall']['recall']:.3f}")
    
    print(f"\nBest Balanced:")
    print(f"  Config: m={analysis['best_balanced']['m']}, "
          f"ef_search={analysis['best_balanced']['ef_search']}")
    print(f"  Speed: {analysis['best_balanced']['avg_search_time_ms']:.2f}ms")
    print(f"  Recall: {analysis['best_balanced']['recall']:.3f}")
    
    print("\n✅ Experiment complete! Results saved to experiments/hnsw/")


if __name__ == "__main__":
    asyncio.run(main())