import asyncio
import logging
from app.services.simulation import simulation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MaintenanceVerification")

async def verify_maintenance_flow():
    logger.info("Starting Maintenance Crew Verification...")
    
    # 1. Initialize Simulation
    await simulation.start()
    logger.info("Simulation started.")
    
    # 2. Get a target machine (Line 1)
    target_machine_id = 1
    
    # 3. Simulate Breakdown
    logger.info(f"Simulating breakdown on Machine {target_machine_id}...")
    simulation.machine_states[target_machine_id].health = 30
    simulation.machine_states[target_machine_id].status = "error"
    simulation.machine_states[target_machine_id].last_issue = "critical_failure"
    
    # 4. Dispatch Crew
    logger.info("Dispatching Maintenance Crew...")
    await simulation.dispatch_maintenance_crew(target_machine_id, priority="high")
    
    # 5. Monitor Crew Status
    logger.info("Monitoring Crew Status for 15 seconds...")
    for _ in range(30): # 30 steps * 0.5s = 15s
        await simulation.update()
        crew = simulation.maintenance_crew
        logger.info(f"Crew Status: {crew['status']} | Pos: ({crew['x']:.1f}, {crew['y']:.1f}) | Action: {crew['current_action']}")
        
        if crew['status'] == 'working':
            logger.info(">>> Crew has arrived and is WORKING!")
        
        if crew['status'] == 'returning' and simulation.machine_states[target_machine_id].health > 90:
             logger.info(">>> Repair COMPLETE! Machine health restored.")
             break
             
        await asyncio.sleep(0.1) # Fast forward
        
    await simulation.stop()
    logger.info("Verification Complete.")

if __name__ == "__main__":
    asyncio.run(verify_maintenance_flow())
